import { defineStore } from 'pinia'
import { ref } from 'vue'
import { kbApi } from '@/api/kbApi'
import type { KbDocument } from '@/types/kb'

export const useKbStore = defineStore('kb', () => {
  const documents = ref<KbDocument[]>([])
  const loading = ref(false)

  async function loadList() {
    loading.value = true
    try {
      const res = await kbApi.list()
      documents.value = res.documents ?? []
    } finally {
      loading.value = false
    }
  }

  async function addText(title: string, content: string) {
    const doc = await kbApi.createText({ title, content })
    documents.value = [doc, ...documents.value.filter((d) => d.id !== doc.id)]
    return doc
  }

  async function uploadFile(file: File, title?: string) {
    const doc = await kbApi.uploadFile(file, title)
    documents.value = [doc, ...documents.value.filter((d) => d.id !== doc.id)]
    return doc
  }

  async function remove(id: string) {
    await kbApi.remove(id)
    documents.value = documents.value.filter((d) => d.id !== id)
  }

  return { documents, loading, loadList, addText, uploadFile, remove }
})
