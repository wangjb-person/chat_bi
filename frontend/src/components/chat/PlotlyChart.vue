<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import Plotly from 'plotly.js-dist-min'

const props = defineProps<{ figureJson: string }>()
const chartRef = ref<HTMLDivElement | null>(null)

async function render() {
  if (!chartRef.value || !props.figureJson) return
  try {
    const fig = JSON.parse(props.figureJson)
    await Plotly.newPlot(chartRef.value, fig.data, fig.layout, { responsive: true })
  } catch (e) {
    console.error('[plotly] render failed', e)
  }
}

onMounted(() => void render())
watch(() => props.figureJson, () => void render())

onUnmounted(() => {
  if (chartRef.value) {
    Plotly.purge(chartRef.value)
  }
})
</script>

<template>
  <div ref="chartRef" class="plot-container" />
</template>

<style scoped>
.plot-container {
  min-height: 320px;
  margin-top: 8px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid var(--color-border);
  padding: 8px;
}
</style>
