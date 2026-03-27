#!/bin/bash
# GeoKD-SR 实验运行脚本
# 用于在 PAI 平台上一键运行实验

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
EXP_DIR="$PROJECT_ROOT/exp"

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 显示帮助
show_help() {
    echo "GeoKD-SR 实验运行脚本"
    echo ""
    echo "用法: $0 [选项] [实验名]"
    echo ""
    echo "实验名:"
    echo "  exp01       运行 Exp01: Direct-SFT（对照组）"
    echo "  exp02       运行 Exp02: Standard-KD（通用蒸馏）"
    echo "  all         运行所有实验"
    echo ""
    echo "选项:"
    echo "  -c, --check     仅运行环境检查"
    echo "  -e, --eval      仅运行评估（需要 --checkpoint）"
    echo "  -r, --resume    恢复训练（需要检查点路径）"
    echo "  --checkpoint    评估时使用的检查点路径"
    echo "  -h, --help      显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 exp01                    # 运行 Exp01 训练"
    echo "  $0 exp02                    # 运行 Exp02 训练"
    echo "  $0 -e exp01 --checkpoint checkpoints/final_model  # 评估 Exp01"
    echo "  $0 -c                       # 仅检查环境"
}

# 环境检查
check_environment() {
    log_info "运行环境检查..."
    python scripts/check_environment.py
    if [ $? -ne 0 ]; then
        log_error "环境检查失败，请先解决问题"
        exit 1
    fi
    log_success "环境检查通过"
}

# 运行训练
run_train() {
    local exp_name=$1
    local exp_dir="$EXP_DIR/$exp_name"
    local resume_flag=""

    if [ -n "$RESUME_PATH" ]; then
        resume_flag="--resume $RESUME_PATH"
    fi

    log_info "开始运行 $exp_name 训练..."
    log_info "工作目录: $exp_dir"

    cd "$exp_dir"

    # 创建日志目录
    mkdir -p logs checkpoints results

    # 运行训练
    log_info "训练开始时间: $(date '+%Y-%m-%d %H:%M:%S')"

    python train.py --config config.yaml $resume_flag 2>&1 | tee "logs/train_$(date '+%Y%m%d_%H%M%S').log"

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log_success "$exp_name 训练完成"
    else
        log_error "$exp_name 训练失败"
        exit 1
    fi

    cd "$PROJECT_ROOT"
}

# 运行评估
run_eval() {
    local exp_name=$1
    local exp_dir="$EXP_DIR/$exp_name"

    if [ -z "$CHECKPOINT_PATH" ]; then
        log_error "请使用 --checkpoint 指定检查点路径"
        exit 1
    fi

    log_info "开始运行 $exp_name 评估..."
    log_info "工作目录: $exp_dir"
    log_info "检查点: $CHECKPOINT_PATH"

    cd "$exp_dir"

    # 创建结果目录
    mkdir -p results

    # 运行评估
    python evaluate.py \
        --config config.yaml \
        --checkpoint "$CHECKPOINT_PATH" \
        --output "results/eval_$(date '+%Y%m%d_%H%M%S').json" \
        2>&1 | tee "logs/eval_$(date '+%Y%m%d_%H%M%S').log"

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log_success "$exp_name 评估完成"
    else
        log_error "$exp_name 评估失败"
        exit 1
    fi

    cd "$PROJECT_ROOT"
}

# 解析参数
CHECK_ENV_ONLY=false
RUN_EVAL=false
RESUME_PATH=""
CHECKPOINT_PATH=""
EXPERIMENT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--check)
            CHECK_ENV_ONLY=true
            shift
            ;;
        -e|--eval)
            RUN_EVAL=true
            shift
            ;;
        -r|--resume)
            RESUME_PATH="$2"
            shift 2
            ;;
        --checkpoint)
            CHECKPOINT_PATH="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        exp01|exp02|all)
            EXPERIMENT="$1"
            shift
            ;;
        *)
            log_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 主逻辑
echo "============================================================"
echo "GeoKD-SR 实验运行脚本"
echo "============================================================"
echo "项目根目录: $PROJECT_ROOT"
echo "实验目录: $EXP_DIR"
echo "============================================================"

# 环境检查
check_environment

# 如果仅检查环境，则退出
if [ "$CHECK_ENV_ONLY" = true ]; then
    log_success "环境检查完成"
    exit 0
fi

# 检查是否指定了实验
if [ -z "$EXPERIMENT" ]; then
    log_error "请指定要运行的实验 (exp01, exp02, 或 all)"
    show_help
    exit 1
fi

# 运行实验
case $EXPERIMENT in
    exp01)
        if [ "$RUN_EVAL" = true ]; then
            run_eval "exp01_direct_sft"
        else
            run_train "exp01_direct_sft"
        fi
        ;;
    exp02)
        if [ "$RUN_EVAL" = true ]; then
            run_eval "exp02_standard_kd"
        else
            run_train "exp02_standard_kd"
        fi
        ;;
    all)
        log_info "运行所有实验..."
        run_train "exp01_direct_sft"
        run_train "exp02_standard_kd"
        log_success "所有实验完成"
        ;;
esac

log_success "脚本执行完成"
