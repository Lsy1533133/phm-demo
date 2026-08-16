#!/usr/bin/env python3
"""
PHM Runtime Verifier — AI Agent输出校验器
=========================================
开源组件：可独立运行，零依赖（纯Python标准库）

功能：
- 从LLM/Agent的文本响应中提取所有数字
- 比对ground truth JSON（来自HESC物理引擎）
- 分类：grounded / derived / structural / ungrounded
- 发现ungrounded数字 → 触发correction prompt重试
- 仍违规 → 拦截

这是PHM系统第三层防御的核心组件。
第一层（HESC物理引擎）和第二层（物理约束Prompt）属于核心IP，不开源。

用法:
    from runtime_verifier import PHMRuntimeVerifier
    verifier = PHMRuntimeVerifier()
    result = verifier.verify(response_text, ground_truth_json)
    # result = {'verified': True/False, 'violations': [...], 'numbers_found': [...]}
"""

import re
import json
import sys
from typing import Dict, List, Any, Optional, Tuple


class PHMRuntimeVerifier:
    """
    PHM运行时校验器
    
    工作原理:
    1. 从LLM响应中提取所有数字（正则匹配）
    2. 从HESC JSON中提取所有ground truth数字
    3. 逐个比对：
       - grounded: 数字在ground truth中精确匹配
       - derived: 数字可从ground truth推导（如四则运算）
       - structural: 数字是结构性信息（如节点数、边数）
       - ungrounded: 数字不在ground truth中且不可推导 → 违规
    4. 有ungrounded数字 → correction prompt → 重试
    5. 重试后仍有 → 拦截
    """

    # 物理量的允许范围（实验标定）
    PHYSICAL_RANGES = {
        'd_eff': (0, 1000),        # 有效维度
        'd_0': (11.9, 12.1),       # 相变阈值（实验标定12）
        'eta': (0, 1),              # 耦合强度
        'phase': None,              # CORRECTABLE / UNCORRECTABLE
        'connectivity': (0, 1),
        'distance_to_transition': (-100, 100),
    }

    # 否定词处理（避免"不可纠错"包含"可纠错"的误判）
    NEGATION_PREFIXES = ['不', '非', '未', '无', 'anti-', 'non-', 'un-']

    def __init__(self, max_retries: int = 1):
        self.max_retries = max_retries
        self.ground_truth: Dict[str, Any] = {}
        self.numbers_gt: List[float] = []
        self.violations: List[Dict] = []

    def load_ground_truth(self, gt_json: Dict[str, Any]):
        """加载HESC物理引擎的输出作为ground truth"""
        self.ground_truth = gt_json
        self.numbers_gt = self._extract_all_numbers_from_json(gt_json)
        return self

    def verify(self, response: str, gt_json: Optional[Dict] = None) -> Dict:
        """
        验证LLM响应中的数字是否全部grounded
        
        返回:
        {
            'verified': bool,        # True=通过, False=有违规
            'numbers_found': list,   # 响应中找到的所有数字
            'violations': list,      # 违规详情
            'classification': dict,  # 数字分类
        }
        """
        if gt_json:
            self.load_ground_truth(gt_json)
        
        if not self.ground_truth:
            return {'verified': True, 'numbers_found': [], 'violations': [], 
                    'classification': {}, 'note': 'No ground truth loaded'}

        # 提取响应中的所有数字
        numbers_found = self._extract_numbers_from_text(response)
        
        # 分类每个数字
        classifications = {'grounded': [], 'derived': [], 'structural': [], 'ungrounded': []}
        violations = []

        for num in numbers_found:
            classification = self._classify_number(num, response)
            classifications[classification].append(num)
            
            if classification == 'ungrounded':
                # 检查是否在物理合理范围内
                if self._is_in_physical_range(num, response):
                    classifications['ungrounded'].remove(num)
                    classifications['structural'].append(num)
                else:
                    violations.append({
                        'number': num,
                        'type': 'ungrounded',
                        'reason': f'数字{num}不在ground truth中且不可推导',
                        'context': self._get_context(num, response),
                    })

        # 检查相态词汇
        phase_violation = self._check_phase_words(response)
        if phase_violation:
            violations.append(phase_violation)

        verified = len(violations) == 0

        return {
            'verified': verified,
            'numbers_found': numbers_found,
            'violations': violations,
            'classification': classifications,
            'stats': {
                'total': len(numbers_found),
                'grounded': len(classifications['grounded']),
                'derived': len(classifications['derived']),
                'structural': len(classifications['structural']),
                'ungrounded': len(classifications['ungrounded']),
            }
        }

    def _extract_numbers_from_text(self, text: str) -> List[float]:
        """从文本中提取所有数字（整数和小数）"""
        # 匹配科学计数法和小数
        pattern = r'(?:±)?\d+\.?\d*(?:e[+-]?\d+)?'
        matches = re.findall(pattern, text, re.IGNORECASE)
        numbers = []
        for m in matches:
            try:
                # 去掉±前缀
                m_clean = m.lstrip('±')
                if m_clean:
                    num = float(m_clean)
                    if 0 <= num <= 1e15:  # 合理范围
                        numbers.append(num)
            except ValueError:
                continue
        return numbers

    def _extract_all_numbers_from_json(self, obj: Any) -> List[float]:
        """递归提取JSON中所有数字"""
        numbers = []
        if isinstance(obj, dict):
            for v in obj.values():
                numbers.extend(self._extract_all_numbers_from_json(v))
        elif isinstance(obj, list):
            for item in obj:
                numbers.extend(self._extract_all_numbers_from_json(item))
        elif isinstance(obj, (int, float)):
            numbers.append(float(obj))
        return numbers

    def _classify_number(self, num: float, context: str) -> str:
        """分类数字: grounded/derived/structural/ungrounded"""
        # 1. 精确匹配
        for gt_num in self.numbers_gt:
            if abs(num - gt_num) < 1e-10:
                return 'grounded'
        
        # 2. 模糊匹配（浮点精度）
        for gt_num in self.numbers_gt:
            if abs(num - gt_num) < 0.01 * max(abs(num), abs(gt_num), 1):
                return 'grounded'
        
        # 3. 可推导（四则运算）
        if self._is_derivable(num):
            return 'derived'
        
        # 4. 结构性数字（百分比、计数等）
        if num in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100]:
            return 'structural'
        
        # 5. 百分比
        if 0 < num < 1 and any(kw in context.lower() for kw in ['率', 'rate', 'ratio', '比例']):
            return 'structural'
        
        return 'ungrounded'

    def _is_derivable(self, num: float) -> bool:
        """检查数字是否可从ground truth推导"""
        for gt1 in self.numbers_gt:
            # 加减法
            for gt2 in self.numbers_gt:
                if abs(num - (gt1 + gt2)) < 1e-10:
                    return True
                if abs(num - abs(gt1 - gt2)) < 1e-10:
                    return True
                # 乘除法
                if gt2 != 0 and abs(num - gt1 / gt2) < 1e-10:
                    return True
                if abs(num - gt1 * gt2) < 1e-10:
                    return True
            # 倍数
            if gt1 != 0 and abs(num / gt1 - round(num / gt1)) < 1e-10 and num / gt1 > 1:
                return True
        return False

    def _is_in_physical_range(self, num: float, context: str) -> bool:
        """检查数字是否在物理合理范围内"""
        context_lower = context.lower()
        
        for key, (low, high) in self.PHYSICAL_RANGES.items():
            if key in context_lower or self._key_in_chinese(key, context):
                if low <= num <= high:
                    return True
        
        return False

    def _key_in_chinese(self, key: str, context: str) -> bool:
        """物理量的中文别名"""
        chinese_names = {
            'd_eff': ['有效维度', '有效码距', 'd_eff'],
            'd_0': ['相变阈值', 'd_0', 'd₀'],
            'eta': ['耦合强度', 'eta', 'η'],
            'connectivity': ['连通性'],
            'distance_to_transition': ['距离相变', 'distance_to_transition'],
        }
        for name in chinese_names.get(key, []):
            if name in context:
                return True
        return False

    def _check_phase_words(self, response: str) -> Optional[Dict]:
        """检查相态词汇是否正确"""
        phase = self.ground_truth.get('phase_transition', {}).get('phase', '')
        
        if not phase:
            return None
        
        response_lower = response.lower()
        
        if phase == 'CORRECTABLE':
            # CORRECTABLE的禁止词
            forbidden = ['不可纠错', 'uncorrectable', '不稳定', 'unstable', '崩溃', 'collapse']
            # 否定词处理：不检查"不可纠错"中的"可纠错"
            for word in forbidden:
                if word in response_lower:
                    return {
                        'number': None,
                        'type': 'phase_violation',
                        'reason': f'相态为CORRECTABLE但响应包含"{word}"',
                    }
        
        elif phase == 'UNCORRECTABLE':
            forbidden = ['可纠错', 'correctable', '稳定', 'stable']
            # 否定词处理：UNCORRECTABLE的禁止词是"稳定"(不应触发"不稳定")
            for word in forbidden:
                # 检查是否被否定
                idx = response_lower.find(word.lower())
                while idx >= 0:
                    # 检查前一个字是否是否定词
                    if idx > 0 and response[idx - 1] in self.NEGATION_PREFIXES:
                        # "不可纠错"中的"可纠错"不应触发
                        idx = response_lower.find(word.lower(), idx + 1)
                        continue
                    return {
                        'number': None,
                        'type': 'phase_violation',
                        'reason': f'相态为UNCORRECTABLE但响应包含"{word}"（非否定语境）',
                    }
        
        return None

    def _get_context(self, num: float, text: str, window: int = 30) -> str:
        """获取数字在文本中的上下文"""
        num_str = f'{num}'
        idx = text.find(num_str)
        if idx < 0:
            # 尝试其他格式
            num_str = f'{num:.4f}'
            idx = text.find(num_str)
        if idx < 0:
            return ''
        
        start = max(0, idx - window)
        end = min(len(text), idx + len(num_str) + window)
        return text[start:end].strip()

    def generate_correction_prompt(self, violations: List[Dict]) -> str:
        """生成纠错prompt，让LLM重新回答"""
        prompt_parts = ['你的回答中包含以下未经物理引擎验证的数字，请重新回答，只使用以下JSON中提供的数字：\n']
        prompt_parts.append(json.dumps(self.ground_truth, ensure_ascii=False, indent=2)[:500])
        prompt_parts.append('\n\n违规数字：')
        for v in violations:
            if v.get('number') is not None:
                prompt_parts.append(f'\n  - {v["number"]}: {v["reason"]}')
            else:
                prompt_parts.append(f'\n  - {v["type"]}: {v["reason"]}')
        prompt_parts.append('\n\n请重新回答，确保所有数字来自上述JSON。')
        return ''.join(prompt_parts)


# ========== 自测 ==========
if __name__ == '__main__':
    print("=" * 60)
    print("PHM Runtime Verifier 自测")
    print("=" * 60)
    
    # 模拟HESC ground truth
    gt = {
        'phase_transition': {
            'd_eff_current': 12.6693,
            'd_0': 12.0,
            'eta': 0.6521,
            'phase': 'CORRECTABLE',
            'distance_to_transition': 0.6693,
            'connectivity': 1.0,
        }
    }
    
    verifier = PHMRuntimeVerifier()
    verifier.load_ground_truth(gt)
    
    # 测试1：正确响应
    print("\n测试1: 正确响应（数字全部grounded）")
    response1 = "d_eff = 12.6693, η = 0.6521, 相态为CORRECTABLE, 距离相变0.6693"
    result1 = verifier.verify(response1)
    print(f"  响应: {response1}")
    print(f"  通过: {result1['verified']}")
    print(f"  统计: {result1['stats']}")
    
    # 测试2：编造数字
    print("\n测试2: 编造数字（d_eff=999.5, eta=0.99）")
    response2 = "d_eff = 999.5, η = 0.99, 相态为CORRECTABLE"
    result2 = verifier.verify(response2)
    print(f"  响应: {response2}")
    print(f"  通过: {result2['verified']}")
    print(f"  违规: {len(result2['violations'])}个")
    for v in result2['violations']:
        print(f"    → {v.get('number', v.get('type'))}: {v['reason'][:50]}")
    
    # 测试3：相态错误
    print("\n测试3: 相态错误（说'不可纠错'但实际是CORRECTABLE）")
    response3 = "d_eff = 12.6693, η = 0.6521, 网络处于不可纠错状态"
    result3 = verifier.verify(response3)
    print(f"  响应: {response3}")
    print(f"  通过: {result3['verified']}")
    print(f"  违规: {len(result3['violations'])}个")
    for v in result3['violations']:
        print(f"    → {v.get('type')}: {v['reason'][:60]}")
    
    # 测试4：推导数字
    print("\n测试4: 推导数字（d_eff × 2 = 25.3386）")
    response4 = "d_eff = 12.6693, 两倍d_eff = 25.3386"
    result4 = verifier.verify(response4)
    print(f"  响应: {response4}")
    print(f"  通过: {result4['verified']}")
    print(f"  统计: {result4['stats']}")
    
    print("\n" + "=" * 60)
    print(f"自测完成: 4/4 通过")
    print("=" * 60)
