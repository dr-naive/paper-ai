import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { ProjectPaperItem, ProjectWorkflowStatus, ResearchProject } from '@/api/projects'

export const useProjectStore = defineStore('project', () => {
  const currentProject = ref<ResearchProject | null>(null)
  const papers = ref<ProjectPaperItem[]>([])
  const workflowStatus = ref<ProjectWorkflowStatus | null>(null)
  const projectId = computed(() => currentProject.value?.id || '')
  const paperCount = computed(() => papers.value.length)
  const phase = computed(() => currentProject.value?.phase || '')
  const researchScope = computed(() => currentProject.value?.research_scope || {
    field: '', research_subject: '', research_question: '', research_goal: '',
    keywords: [], method_direction: '', notes: '',
  })

  const setProject = (project: ResearchProject | null) => { currentProject.value = project }
  const setPapers = (items: ProjectPaperItem[]) => { papers.value = items }
  const setWorkflowStatus = (status: ProjectWorkflowStatus | null) => { workflowStatus.value = status }
  const clear = () => { currentProject.value = null; papers.value = []; workflowStatus.value = null }

  return { currentProject, papers, workflowStatus, projectId, paperCount, phase, researchScope, setProject, setPapers, setWorkflowStatus, clear }
})
