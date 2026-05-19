import { onMounted, ref } from 'vue'
import { healthApi } from '@/api/healthApi'

export function useBackendHealth() {
  const connected = ref(false)
  const statusText = ref('● 检测中...')
  const statusTitle = ref('')
  const pid = ref<number | null>(null)

  async function check(): Promise<boolean> {
    try {
      const data = await healthApi.ping()
      connected.value = true
      pid.value = data.pid
      statusText.value = `● 已连接 pid=${data.pid}`
      statusTitle.value = `后端进程 pid=${data.pid}\n工作目录: ${data.cwd}`
      return true
    } catch (e) {
      connected.value = false
      pid.value = null
      statusText.value = '● 未连接后端'
      statusTitle.value = e instanceof Error ? e.message : String(e)
      return false
    }
  }

  onMounted(() => {
    void check()
  })

  return { connected, statusText, statusTitle, pid, check }
}
