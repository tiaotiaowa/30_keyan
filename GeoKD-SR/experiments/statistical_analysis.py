"""
统计校正模块

用于实验结果的统计分析，包括多重比较校正和各种统计检验方法。

主要功能：
- Holm-Bonferroni校正：解决多重比较问题
- 配对t检验：比较两组配对数据的均值差异
- Wilcoxon符号秩检验：非参数配对检验
- Cohen's d效应量：量化组间差异的大小
- Bonferroni校正：简单的多重比较校正方法
- 统计结果报告：格式化输出统计结果

作者：GeoKD-SR项目组
日期：2026-03-03
"""

import numpy as np
from scipy import stats
from typing import List, Tuple, Dict, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    try:
        import pandas as pd
    except ImportError:
        pd = None  # type: ignore
from dataclasses import dataclass


@dataclass
class StatisticalResult:
    """统计检验结果数据类"""
    test_name: str
    statistic: float
    p_value: float
    effect_size: Optional[float] = None
    significant: bool = False
    alpha: float = 0.05

    def __str__(self) -> str:
        sig = "显著" if self.significant else "不显著"
        result = f"{self.test_name}: statistic={self.statistic:.4f}, p={self.p_value:.4f} ({sig})"
        if self.effect_size is not None:
            result += f", Cohen's d={self.effect_size:.4f}"
        return result


def holm_bonferroni_correction(
    p_values: np.ndarray,
    alpha: float = 0.05
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Holm-Bonferroni多重比较校正

    相比传统Bonferroni校正，Holm-Bonferroni方法具有更高的统计效力，
    同时仍能控制家族错误率(FWER)。

    该方法解决了8组对比在α=0.05水平下整体犯错概率约34%的问题。
    使用Holm-Bonferroni校正后，整体犯错概率可以控制在α水平以内。

    算法步骤：
    1. 对所有p值进行升序排序
    2. 从最小的p值开始，依次检查：p_i <= alpha / (m - i + 1)
    3. 一旦发现不满足条件的p值，停止检验
    4. 所有满足条件的假设都拒绝

    参数
    ----------
    p_values : np.ndarray
        原始p值数组，shape=(m,)，m为假设检验的数量
    alpha : float, default=0.05
        显著性水平

    返回
    ----------
    rejected : np.ndarray
        布尔数组，指示哪些假设被拒绝（True表示拒绝原假设）
    adjusted_p : np.ndarray
        校正后的p值数组

    示例
    ----------
    >>> import numpy as np
    >>> p_values = np.array([0.001, 0.015, 0.030, 0.045, 0.080, 0.120, 0.200, 0.350])
    >>> rejected, adjusted_p = holm_bonferroni_correction(p_values, alpha=0.05)
    >>> print(f"拒绝的假设数量: {sum(rejected)}/{len(p_values)}")
    拒绝的假设数量: 3/8

    参考文献
    ----------
    Holm, S. (1979). A simple sequentially rejective multiple test procedure.
    Scandinavian Journal of Statistics, 6, 65-70.
    """
    p_values = np.asarray(p_values)
    m = len(p_values)

    if m == 0:
        return np.array([], dtype=bool), np.array([])

    # 获取原始索引（用于恢复原始顺序）
    original_indices = np.arange(m)

    # 对p值进行升序排序，记录原始索引
    sorted_indices = np.argsort(p_values)
    sorted_p = p_values[sorted_indices]

    # 初始化结果数组
    rejected = np.zeros(m, dtype=bool)
    adjusted_p = np.zeros(m)

    # Holm-Bonferroni逐步检验
    # 从最小的p值开始检验
    # i从0开始，所以第k步（k=i+1）的阈值是 alpha/(m-k+1) = alpha/(m-i)
    for i, (orig_idx, p) in enumerate(zip(sorted_indices, sorted_p)):
        # 计算该步骤的阈值：alpha / (m - i)
        # i=0时，阈值=alpha/m（最严格）
        # i=m-1时，阈值=alpha/1=alpha（最宽松）
        threshold = alpha / (m - i)

        # 调整后的p值（Holm方法）
        # p_adjusted = max(p * (m - i + 1), previous_adjusted_p)
        # 注意：这里用 (m - i) 因为i从0开始
        if i == 0:
            adjusted_p[orig_idx] = min(p * m, 1.0)
        else:
            # 确保调整后的p值单调递增
            prev_max = np.max(adjusted_p[sorted_indices[:i]])
            adjusted_p[orig_idx] = max(min(p * (m - i), 1.0), prev_max)

        # 检验条件：如果p值大于阈值，停止检验
        if p > threshold:
            # 当前及之后的假设都保留
            # 但仍需要计算剩余的调整后p值
            for j in range(i, m):
                orig_idx_j = sorted_indices[j]
                p_j = sorted_p[j]
                if j == 0:
                    adjusted_p[orig_idx_j] = min(p_j * m, 1.0)
                else:
                    prev_max = np.max(adjusted_p[sorted_indices[:j]])
                    adjusted_p[orig_idx_j] = max(min(p_j * (m - j), 1.0), prev_max)
            break

        # 拒绝原假设
        rejected[orig_idx] = True

    return rejected, adjusted_p


def paired_t_test(
    group1: np.ndarray,
    group2: np.ndarray,
    alpha: float = 0.05,
    alternative: str = 'two-sided'
) -> StatisticalResult:
    """
    配对样本t检验

    用于比较两组配对数据的均值是否存在显著差异。
    适用于数据满足正态性假设的情况。

    参数
    ----------
    group1 : np.ndarray
        第一组数据
    group2 : np.ndarray
        第二组数据（与group1配对）
    alpha : float, default=0.05
        显著性水平
    alternative : str, default='two-sided'
        备择假设类型：'two-sided'(双侧), 'greater'(大于), 'less'(小于)

    返回
    ----------
    StatisticalResult
        包含检验统计量、p值、效应量和显著性的结果对象

    示例
    ----------
    >>> before = np.array([85, 90, 88, 92, 87])
    >>> after = np.array([88, 93, 90, 95, 89])
    >>> result = paired_t_test(after, before)
    >>> print(result)
    """
    group1 = np.asarray(group1)
    group2 = np.asarray(group2)

    if len(group1) != len(group2):
        raise ValueError("两组数据长度必须相同（配对样本）")

    # 执行配对t检验
    statistic, p_value = stats.ttest_rel(group1, group2, alternative=alternative)

    # 计算Cohen's d效应量（配对样本版本）
    diff = group1 - group2
    cohens_d = np.mean(diff) / np.std(diff, ddof=1) if len(diff) > 1 else 0.0

    return StatisticalResult(
        test_name="配对t检验",
        statistic=statistic,
        p_value=p_value,
        effect_size=cohens_d,
        significant=p_value < alpha,
        alpha=alpha
    )


def wilcoxon_test(
    group1: np.ndarray,
    group2: np.ndarray,
    alpha: float = 0.05,
    alternative: str = 'two-sided'
) -> StatisticalResult:
    """
    Wilcoxon符号秩检验（非参数配对检验）

    用于比较两组配对数据的分布是否存在显著差异。
    不要求正态性假设，适用于非正态分布或小样本数据。

    参数
    ----------
    group1 : np.ndarray
        第一组数据
    group2 : np.ndarray
        第二组数据（与group1配对）
    alpha : float, default=0.05
        显著性水平
    alternative : str, default='two-sided'
        备择假设类型

    返回
    ----------
    StatisticalResult
        包含检验统计量、p值和显著性的结果对象

    示例
    ----------
    >>> method_a = np.array([1.2, 1.5, 1.1, 1.8, 1.3])
    >>> method_b = np.array([1.1, 1.3, 1.0, 1.5, 1.2])
    >>> result = wilcoxon_test(method_a, method_b)
    >>> print(result)
    """
    group1 = np.asarray(group1)
    group2 = np.asarray(group2)

    if len(group1) != len(group2):
        raise ValueError("两组数据长度必须相同（配对样本）")

    # 执行Wilcoxon符号秩检验
    statistic, p_value = stats.wilcoxon(group1, group2, alternative=alternative)

    return StatisticalResult(
        test_name="Wilcoxon符号秩检验",
        statistic=statistic,
        p_value=p_value,
        significant=p_value < alpha,
        alpha=alpha
    )


def cohens_d(
    group1: np.ndarray,
    group2: np.ndarray,
    paired: bool = False
) -> float:
    """
    计算Cohen's d效应量

    Cohen's d用于量化两组数据之间的差异大小，
    是标准化的均值差异指标。

    效应量解释：
    - |d| < 0.2: 极小效应
    - 0.2 <= |d| < 0.5: 小效应
    - 0.5 <= |d| < 0.8: 中等效应
    - |d| >= 0.8: 大效应

    参数
    ----------
    group1 : np.ndarray
        第一组数据
    group2 : np.ndarray
        第二组数据
    paired : bool, default=False
        是否为配对样本

    返回
    ----------
    float
        Cohen's d效应量

    示例
    ----------
    >>> control = np.array([100, 105, 98, 102, 99])
    >>> treatment = np.array([110, 115, 108, 112, 109])
    >>> d = cohens_d(treatment, control)
    >>> print(f"Cohen's d = {d:.2f}")
    """
    group1 = np.asarray(group1)
    group2 = np.asarray(group2)

    if paired:
        # 配对样本：使用差值的标准差
        diff = group1 - group2
        d = np.mean(diff) / np.std(diff, ddof=1) if len(diff) > 1 else 0.0
    else:
        # 独立样本：使用合并标准差
        n1, n2 = len(group1), len(group2)
        var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)

        # 合并标准差
        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))

        # Cohen's d
        d = (np.mean(group1) - np.mean(group2)) / pooled_std if pooled_std > 0 else 0.0

    return d


def bonferroni_correction(
    p_values: np.ndarray,
    alpha: float = 0.05
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Bonferroni多重比较校正

    最简单的多重比较校正方法，将显著性水平除以检验次数。
    保守但稳健，适合检验次数较少的情况。

    参数
    ----------
    p_values : np.ndarray
        原始p值数组
    alpha : float, default=0.05
        显著性水平

    返回
    ----------
    rejected : np.ndarray
        布尔数组，指示哪些假设被拒绝
    adjusted_p : np.ndarray
        校正后的p值数组

    示例
    ----------
    >>> p_values = np.array([0.01, 0.03, 0.06, 0.10])
    >>> rejected, adjusted_p = bonferroni_correction(p_values)
    >>> print(f"校正后仍显著的数量: {sum(rejected)}")
    """
    p_values = np.asarray(p_values)
    m = len(p_values)

    if m == 0:
        return np.array([], dtype=bool), np.array([])

    # 调整p值
    adjusted_p = np.minimum(p_values * m, 1.0)

    # 判断是否拒绝原假设
    rejected = adjusted_p <= alpha

    return rejected, adjusted_p


def report_statistics(
    data: np.ndarray,
    name: str = "",
    precision: int = 3,
    include_additional: bool = True
) -> str:
    """
    格式化报告统计结果

    生成包含均值、标准差等统计量的格式化字符串。
    常用格式：均值 ± 标准差

    参数
    ----------
    data : np.ndarray
        数据数组
    name : str, default=""
        数据名称/标签
    precision : int, default=3
        小数点后保留位数
    include_additional : bool, default=True
        是否包含额外统计信息（中位数、IQR）

    返回
    ----------
    str
        格式化的统计报告字符串

    示例
    ----------
    >>> scores = np.array([85, 90, 88, 92, 87, 89, 91, 86])
    >>> print(report_statistics(scores, "实验组"))
    实验组: 88.500 ± 2.138 (n=8)
    """
    data = np.asarray(data)
    n = len(data)
    mean = np.mean(data)
    std = np.std(data, ddof=1)

    # 主报告：均值 ± 标准差
    if name:
        report = f"{name}: {mean:.{precision}f} ± {std:.{precision}f}"
    else:
        report = f"{mean:.{precision}f} ± {std:.{precision}f}"

    # 添加样本量
    report += f" (n={n})"

    # 可选：添加额外统计信息
    if include_additional and n > 0:
        median = np.median(data)
        q1, q3 = np.percentile(data, [25, 75])
        iqr = q3 - q1
        report += f", 中位数={median:.{precision}f}, IQR=[{q1:.{precision}f}, {q3:.{precision}f}]"

    return report


def compare_multiple_groups(
    groups: Dict[str, np.ndarray],
    baseline: str,
    alpha: float = 0.05,
    correction_method: str = 'holm'
) -> 'pd.DataFrame':
    """
    多组比较（使用多重比较校正）

    将多个实验组与基线组进行比较，并应用多重比较校正。

    参数
    ----------
    groups : Dict[str, np.ndarray]
        组别名称到数据的映射，必须包含baseline键
    baseline : str
        基线组的名称
    alpha : float, default=0.05
        显著性水平
    correction_method : str, default='holm'
        校正方法：'holm'(Holm-Bonferroni) 或 'bonferroni'

    返回
    ----------
    pd.DataFrame
        包含比较结果的表格

    示例
    ----------
    >>> groups = {
    ...     'Baseline': np.array([80, 82, 78, 85]),
    ...     'Method A': np.array([85, 87, 83, 88]),
    ...     'Method B': np.array([83, 84, 82, 86]),
    ...     'Method C': np.array([90, 92, 88, 94])
    ... }
    >>> results = compare_multiple_groups(groups, 'Baseline')
    >>> print(results)
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("此功能需要pandas库。请先安装: pip install pandas")

    if baseline not in groups:
        raise ValueError(f"基线组 '{baseline}' 不在groups中")

    baseline_data = groups[baseline]
    results = []
    p_values = []

    # 与每个非基线组进行比较
    for name, data in groups.items():
        if name == baseline:
            continue

        # 执行配对t检验
        result = paired_t_test(data, baseline_data, alpha=alpha)
        results.append({
            'Comparison': f"{name} vs {baseline}",
            'Mean_Diff': np.mean(data) - np.mean(baseline_data),
            't_statistic': result.statistic,
            'p_value': result.p_value,
            'Cohens_d': result.effect_size
        })
        p_values.append(result.p_value)

    # 应用多重比较校正
    if p_values:
        p_values = np.array(p_values)
        if correction_method == 'holm':
            rejected, adjusted_p = holm_bonferroni_correction(p_values, alpha=alpha)
        else:
            rejected, adjusted_p = bonferroni_correction(p_values, alpha=alpha)

        # 添加校正结果
        for i, result in enumerate(results):
            result['adjusted_p'] = adjusted_p[i]
            result['Significant'] = rejected[i]

    return pd.DataFrame(results)


def analyze_geokd_sr_experiment(
    results: Dict[str, np.ndarray],
    baseline: str = "B2",
    alpha: float = 0.05,
    correction_method: str = 'holm'
) -> 'pd.DataFrame':
    """
    GeoKD-SR实验结果分析函数

    专门用于GeoKD-SR消融实验的结果分析，自动应用多重比较校正。

    参数
    ----------
    results : Dict[str, np.ndarray]
        实验结果字典，键为实验名称（如"Exp3", "Exp4"等），值为准确率数组
        例如：{"Exp1": np.array([...]), "Exp2": np.array([...]), ...}
    baseline : str, default="B2"
        基线实验名称，通常是"B2"（Standard-KD）
    alpha : float, default=0.05
        显著性水平
    correction_method : str, default='holm'
        多重比较校正方法：'holm'或'bonferroni'

    返回
    ----------
    pd.DataFrame
        包含比较结果的表格，包括：
        - Comparison: 比较名称
        - Mean_Diff: 均值差异
        - t_statistic: t统计量
        - p_value: 原始p值
        - adjusted_p: 校正后p值
        - Cohens_d: Cohen's d效应量
        - Significant: 是否显著（校正后）

    示例
    ----------
    >>> import numpy as np
    >>> results = {
    ...     "B2": np.array([0.75, 0.76, 0.74, 0.75, 0.76]),
    ...     "Exp3": np.array([0.77, 0.78, 0.76, 0.77, 0.78]),
    ...     "Exp4": np.array([0.78, 0.79, 0.77, 0.78, 0.79]),
    ...     "Exp5": np.array([0.76, 0.77, 0.75, 0.76, 0.77]),
    ... }
    >>> df = analyze_geokd_sr_experiment(results, baseline="B2")
    >>> print(df)
    """
    if baseline not in results:
        raise ValueError(f"基线实验 '{baseline}' 不在results中")

    baseline_data = results[baseline]
    comparisons = []
    p_values = []

    # 实验名称映射（用于更友好的输出）
    name_map = {
        "B1": "Direct-SFT",
        "B2": "Standard-KD",
        "Exp3a": "B2+C1(Uniform)",
        "Exp3": "B2+C1(Learnable)",
        "Exp4": "B2+C2(CoT)",
        "Exp5": "B2+C3(Reverse-KL)",
        "Exp6": "B2+C4(Self-Distill)",
        "Exp7": "B2+C5(Attention)",
        "Exp8": "B2+C6(Progressive)",
        "Exp9": "GeoKD-SR(Full)"
    }

    # 与每个非基线实验进行比较
    for name, data in results.items():
        if name == baseline:
            continue

        # 执行配对t检验
        result = paired_t_test(data, baseline_data, alpha=alpha)

        # 计算均值差异（Exp - Baseline）
        mean_diff = np.mean(data) - np.mean(baseline_data)

        comparisons.append({
            'Comparison': f"{name_map.get(name, name)} vs {name_map.get(baseline, baseline)}",
            'Mean_Diff': mean_diff,
            'Mean_Exp': np.mean(data),
            'Mean_Baseline': np.mean(baseline_data),
            'Std_Exp': np.std(data, ddof=1),
            'Std_Baseline': np.std(baseline_data, ddof=1),
            't_statistic': result.statistic,
            'p_value': result.p_value,
            'Cohens_d': result.effect_size
        })
        p_values.append(result.p_value)

    # 应用多重比较校正
    if p_values:
        p_values = np.array(p_values)
        if correction_method == 'holm':
            rejected, adjusted_p = holm_bonferroni_correction(p_values, alpha=alpha)
        else:
            rejected, adjusted_p = bonferroni_correction(p_values, alpha=alpha)

        # 添加校正结果
        for i, result in enumerate(comparisons):
            result['adjusted_p'] = adjusted_p[i]
            result['Significant'] = rejected[i]
            result 'Sig_Level'] = '***' if result['p_value'] < 0.001 else '**' if result['p_value'] < 0.01 else '*' if result['p_value'] < 0.05 else 'ns'

    return pd.DataFrame(comparisons)


def format_geokd_sr_results(df: 'pd.DataFrame', precision: int = 4) -> str:
    """
    格式化GeoKD-SR实验结果为学术论文表格格式

    参数
    ----------
    df : pd.DataFrame
        analyze_geokd_sr_experiment的输出
    precision : int, default=4
        小数点后保留位数

    返回
    ----------
    str
        格式化的表格字符串

    示例
    ----------
    >>> df = analyze_geokd_sr_experiment(results)
    >>> print(format_geokd_sr_results(df))
    """
    lines = []
    lines.append("=" * 100)
    lines.append("GeoKD-SR消融实验结果统计检验表")
    lines.append("=" * 100)
    lines.append("")

    # 表头
    header = f"{'Comparison':<30} {'Mean±Std':>20} {'Diff':>10} {'t-stat':>10} {'p-value':>12} {'adj-p':>12} {'Sig':>8}"
    lines.append(header)
    lines.append("-" * 100)

    # 数据行
    for _, row in df.iterrows():
        mean_str = f"{row['Mean_Exp']:.{precision}f}±{row['Std_Exp']:.{precision}f"
        diff_str = f"{row['Mean_Diff']:+.{precision}f}"
        t_str = f"{row['t_statistic']:.{precision}f}"
        p_str = f"{row['p_value']:.{precision}f}" if row['p_value'] >= 0.001 else f"{row['p_value']:.2e}"
        adj_p_str = f"{row['adjusted_p']:.{precision}f}" if row['adjusted_p'] >= 0.001 else f"{row['adjusted_p']:.2e}"
        sig_str = row['Sig_Level']

        line = f"{row['Comparison']:<30} {mean_str:>20} {diff_str:>10} {t_str:>10} {p_str:>12} {adj_p_str:>12} {sig_str:>8}"
        lines.append(line)

    lines.append("-" * 100)
    lines.append("")
    lines.append("注:")
    lines.append("1. Mean±Std: 实验组均值±标准差")
    lines.append("2. Diff: 实验组与基线的均值差异")
    lines.append("3. t-stat: 配对t检验统计量")
    lines.append("4. p-value: 原始p值")
    lines.append("5. adj-p: Holm-Bonferroni校正后的p值")
    lines.append("6. Sig: 显著性水平 (*** p<0.001, ** p<0.01, * p<0.05, ns 不显著)")
    lines.append("")
    lines.append("=" * 100)

    return "\n".join(lines)


# ============================================================
# 使用示例和测试
# ============================================================

def _demo_holm_bonferroni():
    """Holm-Bonferroni校正示例"""
    print("=" * 60)
    print("示例1: Holm-Bonferroni校正")
    print("=" * 60)

    # 模拟8组对比的p值（GeoKD-SR实验场景）
    p_values = np.array([0.001, 0.008, 0.015, 0.025, 0.040, 0.060, 0.090, 0.150])
    alpha = 0.05

    print(f"原始p值: {p_values}")
    print(f"显著性水平 α = {alpha}")
    print(f"\n未校正时的显著性: {sum(p_values < alpha)}/{len(p_values)}")

    rejected, adjusted_p = holm_bonferroni_correction(p_values, alpha)

    print(f"\n校正后p值: {adjusted_p}")
    print(f"校正后仍显著的假设: {sum(rejected)}/{len(p_values)}")

    print("\n详细结果:")
    for i, (orig_p, adj_p, rej) in enumerate(zip(p_values, adjusted_p, rejected)):
        status = "[OK] 拒绝" if rej else "[--] 保留"
        threshold = alpha / (len(p_values) - i)
        print(f"  假设{i+1}: p={orig_p:.4f}, adj_p={adj_p:.4f}, "
              f"阈值={threshold:.4f} -> {status}")


def _demo_statistical_tests():
    """统计检验示例"""
    print("\n" + "=" * 60)
    print("示例2: 统计检验方法")
    print("=" * 60)

    np.random.seed(42)

    # 模拟数据：基线方法 vs 改进方法
    n_samples = 20
    baseline = np.random.normal(75, 5, n_samples)
    method_a = baseline + np.random.normal(3, 2, n_samples)  # 真实提升
    method_b = baseline + np.random.normal(0.5, 2, n_samples)  # 微小提升

    print(f"\n基线方法: {report_statistics(baseline, 'Baseline')}")
    print(f"方法A: {report_statistics(method_a, 'Method A')}")
    print(f"方法B: {report_statistics(method_b, 'Method B')}")

    # 配对t检验
    print("\n配对t检验结果:")
    result_a = paired_t_test(method_a, baseline)
    print(f"  Method A vs Baseline: {result_a}")

    result_b = paired_t_test(method_b, baseline)
    print(f"  Method B vs Baseline: {result_b}")

    # Wilcoxon检验
    print("\nWilcoxon符号秩检验结果:")
    wilcoxon_a = wilcoxon_test(method_a, baseline)
    print(f"  Method A vs Baseline: {wilcoxon_a}")


def _demo_multiple_comparisons():
    """多组比较示例"""
    print("\n" + "=" * 60)
    print("示例3: 多组比较与多重比较校正")
    print("=" * 60)

    np.random.seed(42)

    # 模拟GeoKD-SR实验的8个变体
    groups = {'Baseline': np.random.normal(0.75, 0.05, 30)}

    # 添加8个变体，其中有真实改进的
    improvements = [0.02, 0.04, 0.06, 0.01, 0.00, 0.03, 0.05, 0.02]
    for i, imp in enumerate(improvements, 1):
        groups[f'Variant_{i}'] = groups['Baseline'] + np.random.normal(imp, 0.02, 30)

    # 多组比较
    results_df = compare_multiple_groups(groups, 'Baseline', alpha=0.05, correction_method='holm')

    print("\n比较结果（Holm-Bonferroni校正）:")
    print(results_df.to_string(index=False))


def _demo_effect_size():
    """效应量计算示例"""
    print("\n" + "=" * 60)
    print("示例4: Cohen's d效应量")
    print("=" * 60)

    # 不同大小的效应量示例
    scenarios = [
        ("极小效应", np.random.normal(100, 10, 50), np.random.normal(101, 10, 50)),
        ("小效应", np.random.normal(100, 10, 50), np.random.normal(103, 10, 50)),
        ("中等效应", np.random.normal(100, 10, 50), np.random.normal(106, 10, 50)),
        ("大效应", np.random.normal(100, 10, 50), np.random.normal(110, 10, 50)),
    ]

    for name, g1, g2 in scenarios:
        d = cohens_d(g1, g2)
        print(f"{name}: Cohen's d = {d:.3f}")


def _demo_geokd_sr_analysis():
    """GeoKD-SR实验分析示例"""
    print("\n" + "=" * 60)
    print("示例5: GeoKD-SR消融实验分析")
    print("=" * 60)

    np.random.seed(42)

    # 模拟GeoKD-SR实验结果（5次运行的结果）
    # 基线：Standard-KD (B2)
    baseline_acc = np.array([0.752, 0.748, 0.755, 0.750, 0.753])

    # 各消融实验结果
    results = {
        "B2": baseline_acc,
        "Exp3": baseline_acc + np.array([0.015, 0.018, 0.012, 0.016, 0.014]),  # C1: 空间关系蒸馏
        "Exp4": baseline_acc + np.array([0.022, 0.025, 0.020, 0.023, 0.021]),  # C2: 思维链蒸馏
        "Exp5": baseline_acc + np.array([0.018, 0.016, 0.019, 0.017, 0.015]),  # C3: 逆向KL
        "Exp6": baseline_acc + np.array([0.008, 0.010, 0.007, 0.009, 0.008]),   # C4: 自蒸馏损失
        "Exp7": baseline_acc + np.array([0.012, 0.014, 0.011, 0.013, 0.012]),  # C5: 注意力蒸馏
        "Exp8": baseline_acc + np.array([0.010, 0.009, 0.011, 0.010, 0.009]),   # C6: 渐进式蒸馏
        "Exp9": baseline_acc + np.array([0.035, 0.038, 0.033, 0.036, 0.034]),  # 完整方法
    }

    # 分析实验结果
    df = analyze_geokd_sr_experiment(results, baseline="B2", alpha=0.05)

    print("\n实验结果（Holm-Bonferroni校正）:")
    print(format_geokd_sr_results(df))

    # 输出摘要
    print("\n摘要统计:")
    print(f"- 总比较数: {len(df)}")
    print(f"- 显著提升数: {df['Significant'].sum()}")
    print(f"- 最大提升: {df['Mean_Diff'].max():.4f} ({df.loc[df['Mean_Diff'].idxmax(), 'Comparison']})")
    print(f"- 平均提升: {df['Mean_Diff'].mean():.4f}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("统计校正模块 - 功能演示")
    print("=" * 60)

    _demo_holm_bonferroni()
    _demo_statistical_tests()
    _demo_multiple_comparisons()
    _demo_effect_size()
    _demo_geokd_sr_analysis()

    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)
