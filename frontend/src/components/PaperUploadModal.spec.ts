import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PaperUploadModal from './PaperUploadModal.vue'

const uploadPaper = vi.hoisted(() => vi.fn())
const getTaskStatus = vi.hoisted(() => vi.fn())
const addProjectPaper = vi.hoisted(() => vi.fn())
const uploadFile = vi.hoisted(() => new File(['%PDF-1.7'], 'paper.pdf', { type: 'application/pdf' }))

vi.mock('@/api/paper', () => ({
  uploadPaper,
  getTaskStatus,
}))

vi.mock('@/api/projects', () => ({
  addProjectPaper,
}))

const global = {
  stubs: {
    'a-modal': {
      props: ['visible'],
      template: '<section v-if="visible"><slot /></section>',
    },
    'a-spin': { template: '<div><slot /></div>' },
    'a-upload': {
      emits: ['change'],
      setup: () => ({ uploadFile }),
      template: '<button class="upload-stub" type="button" @click="$emit(\'change\', [{ file: uploadFile }])">选择文件</button>',
    },
    'a-button': {
      props: ['disabled'],
      template: '<button :disabled="disabled" type="button" @click="$emit(\'click\')"><slot /></button>',
    },
  },
}

describe('PaperUploadModal', () => {
  beforeEach(() => {
    uploadPaper.mockReset().mockResolvedValue({
      task_id: 'task-paper-1',
      paper_id: 'paper-1',
      message: '上传成功，正在处理论文...',
      status_url: '/api/v1/papers/tasks/task-paper-1',
    })
    getTaskStatus.mockReset().mockResolvedValue({
      task_id: 'task-paper-1',
      paper_id: 'paper-1',
      status: 'ready',
      progress: 100,
      message: '论文已可用',
    })
    addProjectPaper.mockReset().mockResolvedValue({ _action: 'created' })
  })

  it('uploads, waits for readiness and attaches the paper to the active project', async () => {
    const wrapper = mount(PaperUploadModal, {
      props: { visible: true, projectId: 'project-1', projectTitle: '检索研究' },
      global,
    })

    await wrapper.get('.upload-stub').trigger('click')
    await wrapper.get('button:not(.upload-stub)').trigger('click')
    await flushPromises()

    expect(uploadPaper).toHaveBeenCalledWith(uploadFile)
    expect(getTaskStatus).toHaveBeenCalledWith('task-paper-1')
    expect(addProjectPaper).toHaveBeenCalledWith('project-1', { paper_id: 'paper-1' })
    expect(wrapper.emitted('uploaded')).toEqual([[{
      paperId: 'paper-1',
      taskId: 'task-paper-1',
      projectId: 'project-1',
    }]])
  })
})
