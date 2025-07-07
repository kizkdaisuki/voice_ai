#!/bin/bash

# 语音识别助手安装脚本
# 适用于 macOS 系统

echo "🚀 开始安装语音识别助手..."

# 检查 Python 版本
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
if [[ -z "$python_version" ]]; then
    echo "❌ 错误: 未找到 Python3，请先安装 Python 3.7+"
    exit 1
fi

echo "✅ 检测到 Python $python_version"

# 检查是否有 pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ 错误: 未找到 pip3，请先安装 pip"
    exit 1
fi

echo "✅ 检测到 pip3"

# 检查是否有 Homebrew (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v brew &> /dev/null; then
        echo "⚠️  建议安装 Homebrew 以便安装音频依赖"
        echo "   安装命令: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    else
        echo "✅ 检测到 Homebrew"
        
        # 安装 PortAudio (pyaudio 依赖)
        echo "📦 安装 PortAudio..."
        brew install portaudio
    fi
fi

# 创建虚拟环境 (可选)
read -p "🤔 是否创建 Python 虚拟环境? (推荐) [y/N]: " create_venv
if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv voice_ai_env
    source voice_ai_env/bin/activate
    echo "✅ 虚拟环境已激活"
    echo "💡 下次使用前请运行: source voice_ai_env/bin/activate"
fi

# 安装 Python 依赖
echo "📦 安装 Python 依赖包..."
pip3 install -r requirements.txt

# 检查安装结果
echo "🔍 检查安装结果..."

# 检查关键包
packages=("speech_recognition" "pyaudio" "soundcard" "numpy")
all_installed=true

for package in "${packages[@]}"; do
    if python3 -c "import $package" 2>/dev/null; then
        echo "✅ $package - 已安装"
    else
        echo "❌ $package - 安装失败"
        all_installed=false
    fi
done

if $all_installed; then
    echo ""
    echo "🎉 安装完成！"
    echo ""
    echo "📋 使用方法:"
    echo "  python3 voice.py              # 交互式菜单"
    echo "  python3 voice.py -m mic       # 直接启动麦克风识别"
    echo "  python3 voice.py -m system    # 直接启动系统音频识别"
    echo "  python3 voice.py -m mixed     # 直接启动混合识别"
    echo ""
    echo "⚠️  首次运行需要授权麦克风和音频设备权限"
    echo ""
    echo "🔧 macOS 系统音频捕获说明:"
    echo "   如果系统音频识别不工作，可能需要安装 BlackHole:"
    echo "   https://github.com/ExistentialAudio/BlackHole"
    
else
    echo ""
    echo "❌ 安装过程中出现错误，请检查上述失败的包"
    echo "💡 常见解决方案:"
    echo "   - macOS: brew install portaudio"
    echo "   - 手动安装: pip3 install 包名"
    exit 1
fi 