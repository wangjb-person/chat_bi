<template>
  <header class="hero">
    <div class="hero-logo" aria-hidden="true">
      <span class="eye" />
      <span class="eye" />
    </div>
    <h1 class="hero-title">我是 ChatBI，你的 AI 经营分析助手</h1>
    <p class="hero-subtitle">让我陪您一起从数据里发现业务与经营的新洞察</p>
  </header>
</template>

<style scoped>
.hero {
  text-align: center;
  margin-bottom: 28px;
}

.hero-logo {
  width: 56px;
  height: 56px;
  margin: 0 auto 20px;
  border-radius: 50%;
  background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  box-shadow: 0 8px 24px rgba(109, 40, 217, 0.25);
}

.eye {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fff;
}

.hero-title {
  font-size: 28px;
  font-weight: 700;
  color: #1e1b4b;
  letter-spacing: 0.02em;
  margin-bottom: 10px;
}

.hero-subtitle {
  font-size: 15px;
  color: #64748b;
}
</style>
