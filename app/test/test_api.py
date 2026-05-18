from openai import OpenAI

# ====================测试大模型 ====================
API_KEY = "sk-bbcf40088d034f8dafff1597f585e1ff"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"

print("=" * 50)
print("测试阿里云通义千问 API 连接")
print("=" * 50)
print(f"API Key: {API_KEY[:10]}...{API_KEY[-6:]}")
print(f"Base URL: {BASE_URL}")
print(f"Model: {MODEL}")
print("=" * 50)

# 创建客户端
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

# 测试 1: 简单对话
print("\n【测试 1】简单对话...")
try:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "你好，请详细讲一下华强集团今年发展状况"}
        ],
        timeout=30
    )
    print(f"✅ 成功！响应: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ 失败: {e}")