"""
测试拓扑关系匹配逻辑修复

验证问题：
- 参考答案"江苏省与浙江省相邻"（adjacent）
- 模型预测"江苏省位于浙江省内部"（within）
- 修复前：判定为正确（错误）
- 修复后：判定为错误（正确）
"""
import sys
sys.path.insert(0, '.')

from stage2_evaluation.metrics.deterministic import DeterministicMetrics

def test_topology_match():
    """测试拓扑关系类型区分"""
    metrics = DeterministicMetrics()

    # 测试用例
    test_cases = [
        {
            "name": "相同关系类型 - adjacent",
            "reference": "江苏省与浙江省相邻",
            "prediction": "江苏和浙江毗邻",
            "expected": True,
            "reason": "都是adjacent关系，应判定为正确"
        },
        {
            "name": "不同关系类型 - adjacent vs within",
            "reference": "江苏省与浙江省相邻",
            "prediction": "江苏省位于浙江省内部",
            "expected": False,
            "reason": "adjacent vs within，应判定为错误"
        },
        {
            "name": "不同关系类型 - within vs contains",
            "reference": "上海位于江苏内部",
            "prediction": "江苏包含上海",
            "expected": False,
            "reason": "within vs contains，应判定为错误"
        },
        {
            "name": "相同关系类型 - contains",
            "reference": "江苏省包含南京市",
            "prediction": "南京在江苏内部",
            "expected": False,  # contains vs within
            "reason": "contains vs within，应判定为错误"
        },
        {
            "name": "相同关系类型 - within",
            "reference": "上海位于江苏内部",
            "prediction": "上海属于江苏",
            "expected": True,
            "reason": "都是within关系，应判定为正确"
        },
    ]

    print("=" * 70)
    print("拓扑关系匹配测试")
    print("=" * 70)

    passed = 0
    failed = 0

    for case in test_cases:
        result = metrics._check_topological_match(
            case["reference"],
            case["prediction"]
        )

        status = "PASS" if result == case["expected"] else "FAIL"
        if result == case["expected"]:
            passed += 1
        else:
            failed += 1

        print(f"\n[{status}] {case['name']}")
        print(f"  参考答案: {case['reference']}")
        print(f"  预测答案: {case['prediction']}")
        print(f"  期望结果: {case['expected']}")
        print(f"  实际结果: {result}")
        print(f"  说明: {case['reason']}")

        # 显示识别的拓扑类型
        ref_type = metrics._extract_topology_type(case["reference"])
        pred_type = metrics._extract_topology_type(case["prediction"])
        print(f"  参考类型: {ref_type}")
        print(f"  预测类型: {pred_type}")

    print("\n" + "=" * 70)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = test_topology_match()
    sys.exit(0 if success else 1)
