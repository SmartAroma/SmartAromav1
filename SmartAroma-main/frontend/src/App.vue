<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, watchEffect } from 'vue'
import { deleteJson, getJson, postJson, statusWebSocketUrl } from './api/client'

const SCENES = [
  {
    key: '睡前安睡',
    title: '睡前安睡',
    desc: '像夜色慢慢落下，适合把紧绷感一点点放下。',
    accent: 'sleep',
    mood: '夜雾安睡',
  },
  {
    key: '通勤提神',
    title: '通勤提神',
    desc: '轻快而不刺激，让精神慢慢亮起来。',
    accent: 'commute',
    mood: '清醒流动',
  },
  {
    key: '阅读专注',
    title: '阅读专注',
    desc: '保持清晰与稳定，把注意力温柔收拢。',
    accent: 'focus',
    mood: '静定专注',
  },
  {
    key: '静心冥想',
    title: '静心冥想',
    desc: '节奏慢下来，让呼吸与气味一起变轻。',
    accent: 'meditation',
    mood: '沉静内收',
  },
  {
    key: '晨间唤醒',
    title: '晨间唤醒',
    desc: '带一点晨光的暖意，适合开启新的一段状态。',
    accent: 'morning',
    mood: '晨光苏醒',
  },
] as const

const PERSONAS = [
  {
    key: '专业调香师',
    title: '专业调香师',
    desc: '更专业、更克制，强调香气层次与节奏。',
    vibe: '理性陪伴',
  },
  {
    key: '温柔恋人',
    title: '温柔恋人',
    desc: '更柔和、更细腻，像被轻轻照顾着。',
    vibe: '柔软陪伴',
  },
  {
    key: '松弛老友',
    title: '松弛老友',
    desc: '更自然、更轻松，像有人熟悉地陪你聊两句。',
    vibe: '轻松陪伴',
  },
] as const

const DURATION_LEVELS = [
  { key: '速享', title: '速享', desc: '短时快速进入状态' },
  { key: '标准', title: '标准', desc: '平衡、自然、适合大多数情况' },
  { key: '沉浸', title: '沉浸', desc: '更完整地展开这段香气体验' },
] as const

const GENERATING_HINTS = [
  '正在理解你此刻的场景和情绪节奏…',
  '正在组织更适合你的香气层次与扩散顺序…',
  '正在用当前人格语气生成这次香氛说明…',
] as const

const AROMA_LABELS: Record<string, string> = {
  lavender: '薰衣草',
  rose: '玫瑰',
  chamomile: '洋甘菊',
  sandalwood: '檀香',
  citrus: '柑橘',
  mint: '薄荷',
  frankincense: '乳香',
  lemon: '柠檬',
  rosemary: '迷迭香',
}

interface StartPayload {
  scene: string
  persona: string
  duration_level: string
}

interface StatusPayload {
  phase: string
  scene: string | null
  preference: string | null
  persona: string | null
  duration_level: string | null
  plan_name: string | null
  mood_tag: string | null
  opening_line: string | null
  explanation: string | null
  closing_line: string | null
  total_duration_sec: number
  sequence: SequenceStep[]
  current_aroma: string | null
  fan_speed: number
  segment_index: number
  segment_count: number
  segment_remaining_sec: number
  total_remaining_sec: number
  error_message: string | null
}

interface SequenceStep {
  aroma: string
  fan_speed: number
  duration_sec: number
}

interface AromaPlanPayload {
  scene: string
  preference: string
  persona: string
  duration_level: string
  plan_name: string
  mood_tag: string
  opening_line: string
  explanation: string
  closing_line: string
  total_duration_sec: number
  sequence: SequenceStep[]
}

interface UserProfile {
  id: string
  username: string
  display_name: string
  created_at: string
}

interface AuthResponse {
  token: string
  user: UserProfile
}

interface HistoryEntry {
  id: string
  created_at: string
  scene: string
  persona: string
  duration_level: string
  plan_name: string | null
  mood_tag: string | null
  explanation: string | null
  total_duration_sec: number | null
  plan?: AromaPlanPayload | null
}

interface CabinContext {
  time_period: string
  drive_mode: string
  driver_state: string
  air_quality: string
  temperature_c: number
  humidity: number
  co2_ppm: number
}

interface CabinRecommendation {
  scene: string
  persona: string
  duration_level: string
  confidence: number
  cabin_score: number
  alert_level: string
  summary: string
  reasons: string[]
  environment_tags: string[]
}

interface CabinSnapshot {
  scenario_id: string
  scenario_name: string
  updated_at: string
  context: CabinContext
  recommendation: CabinRecommendation
}

const TOKEN_STORAGE_KEY = 'smart_aroma_token'

const selectedScene = ref<string>(SCENES[0].key)
const selectedPersona = ref<string>(PERSONAS[1].key)
const selectedDurationLevel = ref<string>(DURATION_LEVELS[1].key)
const status = ref<StatusPayload | null>(null)
const lastAction = ref('')
const wsError = ref('')
const generatingHintIndex = ref(0)
const authMode = ref<'login' | 'register'>('login')
const authToken = ref('')
const authUser = ref<UserProfile | null>(null)
const authUsername = ref('')
const authPassword = ref('')
const authDisplayName = ref('')
const authLoading = ref(false)
const authMessage = ref('')
const historyEntries = ref<HistoryEntry[]>([])
const historyLoading = ref(false)
const historyMessage = ref('')
const historySavedForRun = ref(false)
const appliedHistoryId = ref('')
const historyExpanded = ref(false)
const cabinContext = ref<CabinContext>({
  time_period: '早晨',
  drive_mode: '城市通勤',
  driver_state: '轻度疲劳',
  air_quality: '一般',
  temperature_c: 27,
  humidity: 58,
  co2_ppm: 980,
})
const cabinRecommendation = ref<CabinRecommendation | null>(null)
const cabinSnapshot = ref<CabinSnapshot | null>(null)
const cabinLoading = ref(false)
const cabinMessage = ref('')
let cabinRefreshTimer: number | null = null

let ws: WebSocket | null = null
let wsShouldReconnect = true
let generatingHintTimer: number | null = null

const phaseLabel: Record<string, string> = {
  idle: '待命中',
  generating: '正在生成方案',
  running: '陪伴运行中',
  paused: '已暂停',
  completed: '已完成',
  stopped: '已停止',
  error: '错误',
}

const isAuthenticated = computed(() => Boolean(authToken.value && authUser.value))
const phase = computed(() => status.value?.phase ?? 'idle')
const isGenerating = computed(() => phase.value === 'generating')
const isRunningLike = computed(() => ['running', 'paused'].includes(phase.value))
const isIdleLike = computed(() => !isGenerating.value && !isRunningLike.value)
const canStart = computed(() => isAuthenticated.value && !['generating', 'running', 'paused'].includes(phase.value))
const canPause = computed(() => phase.value === 'running')
const canResume = computed(() => phase.value === 'paused')
const canStop = computed(() => ['generating', 'running', 'paused'].includes(phase.value))

const currentSceneMeta = computed(() => {
  const current = isRunningLike.value ? (status.value?.scene ?? selectedScene.value) : selectedScene.value
  return SCENES.find((item) => item.key === current) ?? SCENES[0]
})

const currentPersonaMeta = computed(() => {
  const current = isRunningLike.value ? (status.value?.persona ?? selectedPersona.value) : selectedPersona.value
  return PERSONAS.find((item) => item.key === current) ?? PERSONAS[0]
})

const currentDurationMeta = computed(() => {
  const current = isRunningLike.value ? (status.value?.duration_level ?? selectedDurationLevel.value) : selectedDurationLevel.value
  return DURATION_LEVELS.find((item) => item.key === current) ?? DURATION_LEVELS[0]
})

const sceneThemeClass = computed(() => `theme-${currentSceneMeta.value.accent}`)
const generatingHint = computed(() => GENERATING_HINTS[generatingHintIndex.value % GENERATING_HINTS.length])
const cleanedExplanation = computed(() => {
  const raw = status.value?.explanation ?? ''
  return raw.replace(/^MOCK_PLAN:\s*/u, '').trim()
})
const persistentFeedback = computed(() => {
  if (status.value?.error_message) return status.value.error_message
  if (wsError.value) return wsError.value
  return ''
})
const progressText = computed(() => {
  if (!status.value || status.value.segment_count <= 0) return '等待方案生成'
  return `${Math.max(0, status.value.segment_index) + 1} / ${status.value.segment_count}`
})
const cabinScoreLabel = computed(() => {
  const score = cabinSnapshot.value?.recommendation.cabin_score ?? cabinRecommendation.value?.cabin_score ?? estimatedCabinScore()
  if (score >= 80) return '舒适'
  if (score >= 60) return '注意'
  return '需通风'
})
const co2Level = computed(() => {
  const value = cabinContext.value.co2_ppm
  if (value >= 1200) return '偏高'
  if (value >= 900) return '一般'
  return '良好'
})
const temperatureLevel = computed(() => {
  const value = cabinContext.value.temperature_c
  if (value >= 30) return '偏热'
  if (value <= 16) return '偏冷'
  return '舒适'
})

function formatMmSs(sec: number): string {
  const s = Math.max(0, Math.floor(sec))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${r.toString().padStart(2, '0')}`
}

function aromaLabel(id: string | null): string {
  if (!id) return '—'
  return AROMA_LABELS[id] ?? id
}

function estimatedCabinScore(): number {
  let score = 92
  if (cabinContext.value.air_quality === '一般') score -= 8
  if (cabinContext.value.air_quality === '闷浊') score -= 18
  if (cabinContext.value.co2_ppm >= 900) score -= 6
  if (cabinContext.value.co2_ppm >= 1200) score -= 10
  if (cabinContext.value.temperature_c >= 30 || cabinContext.value.temperature_c <= 16) score -= 6
  if (cabinContext.value.humidity >= 75 || cabinContext.value.humidity <= 30) score -= 5
  return Math.max(35, Math.min(100, score))
}

function formatSnapshotTime(value: string | undefined): string {
  if (!value) return '等待读取'
  return new Date(value).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function startGeneratingHints() {
  stopGeneratingHints()
  generatingHintIndex.value = 0
  generatingHintTimer = window.setInterval(() => {
    generatingHintIndex.value = (generatingHintIndex.value + 1) % GENERATING_HINTS.length
  }, 2200)
}

function stopGeneratingHints() {
  if (generatingHintTimer !== null) {
    window.clearInterval(generatingHintTimer)
    generatingHintTimer = null
  }
}

function connectWs() {
  wsShouldReconnect = true
  if (ws) {
    ws.onclose = null
    ws.close()
  }
  wsError.value = ''
  ws = new WebSocket(statusWebSocketUrl())
  ws.onmessage = (ev) => {
    try {
      status.value = JSON.parse(ev.data) as StatusPayload
    } catch {
      wsError.value = '无法解析状态数据'
    }
  }
  ws.onerror = () => {
    wsError.value = 'WebSocket 连接异常（请确认后端已启动）'
  }
  ws.onclose = () => {
    if (!wsShouldReconnect) return
    if (wsError.value === '') wsError.value = '连接已断开，正在重试…'
    setTimeout(() => {
      if (wsShouldReconnect) connectWs()
    }, 2000)
  }
}

function disconnectWs() {
  wsShouldReconnect = false
  if (ws) {
    ws.onclose = null
    ws.close()
    ws = null
  }
}

async function refreshOnce() {
  try {
    status.value = await getJson<StatusPayload>('/api/state')
    lastAction.value = ''
  } catch {
    lastAction.value = '无法拉取状态，请启动后端'
  }
}

function setAuthSession(response: AuthResponse) {
  authToken.value = response.token
  authUser.value = response.user
  window.localStorage.setItem(TOKEN_STORAGE_KEY, response.token)
}

function clearAuthSession() {
  authToken.value = ''
  authUser.value = null
  historyEntries.value = []
  historyMessage.value = ''
  window.localStorage.removeItem(TOKEN_STORAGE_KEY)
  stopCabinRefresh()
  disconnectWs()
}

async function loadHistory() {
  if (!authToken.value) return
  historyLoading.value = true
  try {
    historyEntries.value = await getJson<HistoryEntry[]>('/api/history', { token: authToken.value })
  } catch (error) {
    historyMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    historyLoading.value = false
  }
}

async function restoreSession() {
  const storedToken = window.localStorage.getItem(TOKEN_STORAGE_KEY)
  if (!storedToken) return
  authToken.value = storedToken
  try {
    authUser.value = await getJson<UserProfile>('/api/auth/me', { token: storedToken })
    await loadHistory()
    await loadCabinSnapshot()
    startCabinRefresh()
    await refreshOnce()
    connectWs()
  } catch {
    clearAuthSession()
    authMessage.value = '登录状态已失效，请重新登录'
  }
}

async function loadCabinSnapshot() {
  if (!authToken.value) return
  try {
    const snapshot = await getJson<CabinSnapshot>('/api/cabin/snapshot', { token: authToken.value })
    cabinSnapshot.value = snapshot
    cabinContext.value = snapshot.context
    cabinRecommendation.value = snapshot.recommendation
  } catch (error) {
    cabinMessage.value = error instanceof Error ? error.message : String(error)
  }
}

function startCabinRefresh() {
  if (cabinRefreshTimer !== null) window.clearInterval(cabinRefreshTimer)
  cabinRefreshTimer = window.setInterval(() => {
    if (isAuthenticated.value && canStart.value) void loadCabinSnapshot()
  }, 12000)
}

function stopCabinRefresh() {
  if (cabinRefreshTimer !== null) {
    window.clearInterval(cabinRefreshTimer)
    cabinRefreshTimer = null
  }
}

async function onAuthSubmit() {
  authLoading.value = true
  authMessage.value = ''
  try {
    const endpoint = authMode.value === 'login' ? '/api/auth/login' : '/api/auth/register'
    const response = await postJson<AuthResponse>(endpoint, {
      username: authUsername.value,
      password: authPassword.value,
      display_name: authMode.value === 'register' ? authDisplayName.value : undefined,
    })
    setAuthSession(response)
    authPassword.value = ''
    authMessage.value = authMode.value === 'login' ? '登录成功' : '注册成功，已进入系统'
    await loadHistory()
    await loadCabinSnapshot()
    startCabinRefresh()
    await refreshOnce()
    connectWs()
  } catch (error) {
    authMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    authLoading.value = false
  }
}

async function onLogout() {
  if (authToken.value) {
    try {
      await postJson<{ ok: boolean; message: string }>('/api/auth/logout', {}, { token: authToken.value })
    } catch {
      // Local logout should still work if the backend is unavailable.
    }
  }
  clearAuthSession()
  stopCabinRefresh()
  status.value = null
  lastAction.value = '已退出登录'
}

async function onStart() {
  const payload: StartPayload = {
    scene: selectedScene.value,
    persona: selectedPersona.value,
    duration_level: selectedDurationLevel.value,
  }
  try {
    historySavedForRun.value = false
    appliedHistoryId.value = ''
    const response = await postJson<{ ok: boolean; message: string }>('/api/start', payload)
    lastAction.value = response.message
  } catch (error) {
    lastAction.value = error instanceof Error ? error.message : String(error)
  }
}

async function onSmartGenerate() {
  if (!authToken.value || !canStart.value) return
  cabinLoading.value = true
  cabinMessage.value = ''
  try {
    if (!cabinSnapshot.value) await loadCabinSnapshot()
    const recommendation = cabinSnapshot.value?.recommendation
    if (!recommendation) throw new Error('暂未读取到车载环境数据')
    cabinRecommendation.value = recommendation
    selectedScene.value = recommendation.scene
    selectedPersona.value = recommendation.persona
    selectedDurationLevel.value = recommendation.duration_level
    historySavedForRun.value = false
    appliedHistoryId.value = ''
    const response = await postJson<{ ok: boolean; message: string }>('/api/start', {
      scene: recommendation.scene,
      persona: recommendation.persona,
      duration_level: recommendation.duration_level,
    })
    lastAction.value = `智能推荐：${recommendation.scene} · ${recommendation.persona} · ${recommendation.duration_level}`
    cabinMessage.value = response.message
  } catch (error) {
    cabinMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    cabinLoading.value = false
  }
}

async function onPause() {
  try {
    const response = await postJson<{ ok: boolean; message: string }>('/api/pause')
    lastAction.value = response.message
  } catch (error) {
    lastAction.value = error instanceof Error ? error.message : String(error)
  }
}

async function onResume() {
  try {
    const response = await postJson<{ ok: boolean; message: string }>('/api/resume')
    lastAction.value = response.message
  } catch (error) {
    lastAction.value = error instanceof Error ? error.message : String(error)
  }
}

async function onStop() {
  try {
    const response = await postJson<{ ok: boolean; message: string }>('/api/stop')
    lastAction.value = response.message
  } catch (error) {
    lastAction.value = error instanceof Error ? error.message : String(error)
  }
}

async function saveCurrentHistory(snapshot: StatusPayload) {
  if (!authToken.value || historySavedForRun.value) return
  if (!snapshot.scene || !snapshot.persona || !snapshot.duration_level || !snapshot.plan_name) return
  if (snapshot.segment_count <= 0) return

  const plan = planFromStatus(snapshot)
  historySavedForRun.value = true
  try {
    const entry = await postJson<HistoryEntry>(
      '/api/history',
      {
        scene: snapshot.scene,
        persona: snapshot.persona,
        duration_level: snapshot.duration_level,
        plan_name: snapshot.plan_name,
        mood_tag: snapshot.mood_tag,
        explanation: snapshot.explanation,
        total_duration_sec: snapshot.total_duration_sec,
        plan,
      },
      { token: authToken.value },
    )
    historyEntries.value = [entry, ...historyEntries.value.filter((item) => item.id !== entry.id)].slice(0, 30)
  } catch (error) {
    historySavedForRun.value = false
    historyMessage.value = error instanceof Error ? error.message : String(error)
  }
}

async function deleteHistoryEntry(entryId: string) {
  if (!authToken.value) return
  try {
    await deleteJson<{ ok: boolean; message: string }>(`/api/history/${entryId}`, { token: authToken.value })
    historyEntries.value = historyEntries.value.filter((item) => item.id !== entryId)
  } catch (error) {
    historyMessage.value = error instanceof Error ? error.message : String(error)
  }
}

function planFromStatus(snapshot: StatusPayload): AromaPlanPayload | null {
  if (
    !snapshot.scene ||
    !snapshot.preference ||
    !snapshot.persona ||
    !snapshot.duration_level ||
    !snapshot.plan_name ||
    !snapshot.mood_tag ||
    !snapshot.opening_line ||
    !snapshot.closing_line
  ) {
    return null
  }

  if (!snapshot.sequence?.length) return null

  return {
    scene: snapshot.scene,
    preference: snapshot.preference,
    persona: snapshot.persona,
    duration_level: snapshot.duration_level,
    plan_name: snapshot.plan_name,
    mood_tag: snapshot.mood_tag,
    opening_line: snapshot.opening_line,
    explanation: snapshot.explanation || '',
    closing_line: snapshot.closing_line,
    total_duration_sec: snapshot.total_duration_sec,
    sequence: snapshot.sequence,
  }
}

async function startHistoryEntry(entry: HistoryEntry) {
  selectedScene.value = entry.scene
  selectedPersona.value = entry.persona
  selectedDurationLevel.value = entry.duration_level
  appliedHistoryId.value = entry.id
  if (!entry.plan?.sequence?.length) {
    lastAction.value = '这条历史缺少完整方案，请重新生成一次后再复用运行'
    return
  }
  try {
    historySavedForRun.value = true
    const response = await postJson<{ ok: boolean; message: string }>(
      `/api/history/${entry.id}/start`,
      {},
      { token: authToken.value },
    )
    lastAction.value = response.message
  } catch (error) {
    historySavedForRun.value = false
    lastAction.value = error instanceof Error ? error.message : String(error)
  }
}

onMounted(() => {
  void restoreSession()
})

onUnmounted(() => {
  wsShouldReconnect = false
  stopGeneratingHints()
  stopCabinRefresh()
  if (ws) {
    disconnectWs()
  }
})

const stopGenerating = computed(() => !isGenerating.value)

watchEffect(() => {
  if (isGenerating.value) {
    startGeneratingHints()
  }
  if (stopGenerating.value) {
    stopGeneratingHints()
  }
})

watch(status, (snapshot) => {
  if (!snapshot || snapshot.phase !== 'running') return
  void saveCurrentHistory(snapshot)
})
</script>

<template>
  <div class="app-shell" :class="sceneThemeClass">
    <div class="mist mist-1" />
    <div class="mist mist-2" />
    <div class="mist mist-3" />

    <main class="app-frame">
      <header class="brand-row">
        <div>
          <p class="brand-mark">SmartAroma</p>
          <h1 class="brand-title">小屏智能香氛伴侣</h1>
        </div>
        <div class="header-actions">
          <span v-if="isAuthenticated" class="phase-pill user-pill">{{ authUser?.display_name }}</span>
          <span class="phase-pill">{{ phaseLabel[phase] ?? phase }}</span>
          <button v-if="isAuthenticated" type="button" class="mini-action" @click="onLogout">退出</button>
        </div>
      </header>

      <section v-if="!isAuthenticated" class="auth-view soft-card">
        <div class="auth-copy">
          <p class="section-eyebrow">Account</p>
          <h2>登录后记录你的专属香氛历史</h2>
          <p>
            每个账号会独立保存生成过的场景、人设、时长和方案说明，适合在课程展示里演示多用户个性化记录。
          </p>
        </div>

        <form class="auth-form" @submit.prevent="onAuthSubmit">
          <div class="auth-tabs" role="tablist">
            <button type="button" :class="{ active: authMode === 'login' }" @click="authMode = 'login'">
              登录
            </button>
            <button type="button" :class="{ active: authMode === 'register' }" @click="authMode = 'register'">
              注册
            </button>
          </div>

          <label class="field-label">
            <span>用户名</span>
            <input v-model.trim="authUsername" type="text" autocomplete="username" required minlength="3" />
          </label>
          <label v-if="authMode === 'register'" class="field-label">
            <span>显示名</span>
            <input v-model.trim="authDisplayName" type="text" autocomplete="name" placeholder="可选" />
          </label>
          <label class="field-label">
            <span>密码</span>
            <input
              v-model="authPassword"
              type="password"
              autocomplete="current-password"
              required
              minlength="4"
            />
          </label>

          <button type="submit" class="primary-action" :disabled="authLoading">
            {{ authMode === 'login' ? '进入系统' : '创建账号' }}
          </button>
          <p v-if="authMessage" class="feedback" :class="{ error: authMessage.includes('错误') }">
            {{ authMessage }}
          </p>
        </form>
      </section>

      <Transition name="view-fade" mode="out-in">
        <section v-if="isAuthenticated && isIdleLike" class="idle-view" key="idle">
          <aside class="history-sidebar" :class="{ expanded: historyExpanded }">
            <button type="button" class="soft-card history-rail" @click="historyExpanded = !historyExpanded">
              <span class="history-rail-icon">{{ historyExpanded ? '‹' : '›' }}</span>
              <span class="history-rail-text">历史记录</span>
              <small>{{ historyEntries.length }}</small>
            </button>

            <article v-if="historyExpanded" class="soft-card history-card">
              <div class="story-head">
                <div>
                  <p class="section-eyebrow">History</p>
                  <h3>我的历史记录</h3>
                </div>
                <button type="button" class="mini-action" :disabled="historyLoading" @click="loadHistory">刷新</button>
              </div>
              <p v-if="historyMessage" class="feedback warn">{{ historyMessage }}</p>
              <div v-if="historyEntries.length === 0" class="empty-history">
                登录后生成的方案会保存在这里，不同用户之间互不影响。
              </div>
              <div v-else class="history-list">
                <div v-for="entry in historyEntries" :key="entry.id" class="history-item">
                  <div>
                    <span class="metric-label">{{ formatDate(entry.created_at) }}</span>
                    <strong>{{ entry.plan_name || entry.scene }}</strong>
                    <p>{{ entry.scene }} · {{ entry.persona }} · {{ entry.duration_level }}</p>
                    <p v-if="appliedHistoryId === entry.id" class="history-applied">已复用完整方案并开始运行</p>
                    <p v-else-if="!entry.plan?.sequence?.length" class="history-applied history-missing">
                      旧记录缺少完整序列，需重新生成后才能直接运行
                    </p>
                  </div>
                  <div class="history-actions">
                    <button type="button" class="mini-action" :disabled="!canStart" @click="startHistoryEntry(entry)">
                      {{ appliedHistoryId === entry.id ? '运行中' : '复用运行' }}
                    </button>
                    <button type="button" class="mini-action danger-text" @click="deleteHistoryEntry(entry.id)">
                      删除
                    </button>
                  </div>
                </div>
              </div>
            </article>
          </aside>

          <div class="manual-panel">
              <article class="hero-card soft-card">
                <div class="hero-copy">
                  <p class="hero-tag">{{ currentSceneMeta.mood }}</p>
                  <h2>{{ currentSceneMeta.title }}</h2>
                  <p class="hero-desc">{{ currentSceneMeta.desc }}</p>
                  <p class="hero-support">
                    选择一个此刻更贴近你的场景，让香气与角色语气一起，把状态温柔地带到合适的位置。
                  </p>
                </div>
                <div class="hero-orb" />
              </article>

              <section class="composer-grid">
                <article class="soft-card section-card scene-section">
                  <div class="section-head">
                    <div>
                      <p class="section-eyebrow">Scene</p>
                      <h3>选择场景</h3>
                    </div>
                    <span class="section-note">主选择项</span>
                  </div>
                  <div class="scene-stack">
                    <button
                      v-for="scene in SCENES"
                      :key="scene.key"
                      type="button"
                      class="scene-option"
                      :class="{ active: selectedScene === scene.key }"
                      :disabled="!canStart"
                      @click="selectedScene = scene.key"
                    >
                      <span class="scene-option-title">{{ scene.title }}</span>
                      <span class="scene-option-desc">{{ scene.desc }}</span>
                    </button>
                  </div>
                </article>

                <article class="soft-card section-card option-section">
                  <div class="section-head compact-head">
                    <div>
                      <p class="section-eyebrow">Persona</p>
                      <h3>角色人格</h3>
                    </div>
                    <span class="section-note">辅助选择</span>
                  </div>
                  <div class="persona-stack">
                    <button
                      v-for="persona in PERSONAS"
                      :key="persona.key"
                      type="button"
                      class="persona-option"
                      :class="{ active: selectedPersona === persona.key }"
                      :disabled="!canStart"
                      @click="selectedPersona = persona.key"
                    >
                      <span class="persona-title">{{ persona.title }}</span>
                      <span class="persona-desc">{{ persona.desc }}</span>
                      <span class="persona-vibe">{{ persona.vibe }}</span>
                    </button>
                  </div>

                  <div class="section-head compact-head duration-head">
                    <div>
                      <p class="section-eyebrow">Duration</p>
                      <h3>时长档位</h3>
                    </div>
                  </div>
                  <div class="duration-row">
                    <button
                      v-for="duration in DURATION_LEVELS"
                      :key="duration.key"
                      type="button"
                      class="duration-option"
                      :class="{ active: selectedDurationLevel === duration.key }"
                      :disabled="!canStart"
                      @click="selectedDurationLevel = duration.key"
                    >
                      <span class="duration-title">{{ duration.title }}</span>
                      <span class="duration-desc">{{ duration.desc }}</span>
                    </button>
                  </div>
                </article>
              </section>

              <article class="soft-card action-card">
                <div class="action-copy">
                  <p class="action-label">即将生成</p>
                  <h3>{{ currentSceneMeta.title }} · {{ currentPersonaMeta.title }}</h3>
                  <p>{{ currentDurationMeta.desc }}</p>
                  <p v-if="lastAction" class="action-feedback">{{ lastAction }}</p>
                </div>
                <button type="button" class="primary-action" :disabled="!canStart" @click="onStart">
                  生成今天的香氛陪伴
                </button>
              </article>
          </div>

          <aside class="cabin-view">
            <article class="cabin-dashboard soft-card">
              <div class="cabin-topbar">
                <div>
                  <p class="section-eyebrow">Smart Cabin</p>
                  <h2>车载环境感知舱</h2>
                </div>
                <div class="cabin-top-actions">
                  <span class="phase-pill">{{ cabinSnapshot?.scenario_name || '读取中' }}</span>
                </div>
              </div>

              <section class="cabin-stage">
                <div class="airflow-field airflow-left">
                  <span />
                  <span />
                  <span />
                </div>
                <div class="airflow-field airflow-right">
                  <span />
                  <span />
                  <span />
                </div>

                <div class="car-visual" aria-label="车载环境可视化">
                  <div class="car-glow" />
                  <svg viewBox="0 0 720 260" role="img">
                    <path class="car-shadow" d="M126 205 C190 232 526 232 604 205" />
                    <path
                      class="car-body"
                      d="M78 162 C116 112 159 92 236 88 L327 48 C385 24 486 38 535 92 C592 99 642 121 668 159 C681 179 670 201 644 205 L118 205 C81 203 58 187 78 162 Z"
                    />
                    <path class="car-window" d="M252 91 L334 55 C377 41 462 49 504 94 L423 103 L246 103 Z" />
                    <path class="car-line" d="M124 159 C217 142 507 139 632 161" />
                    <circle class="wheel" cx="194" cy="203" r="39" />
                    <circle class="wheel-core" cx="194" cy="203" r="15" />
                    <circle class="wheel" cx="557" cy="203" r="39" />
                    <circle class="wheel-core" cx="557" cy="203" r="15" />
                  </svg>
                  <div class="cabin-mist cabin-mist-a" />
                  <div class="cabin-mist cabin-mist-b" />
                </div>

                <div class="cabin-score-panel">
                  <span>舒适指数</span>
                  <strong>{{ cabinSnapshot?.recommendation.cabin_score ?? estimatedCabinScore() }}</strong>
                  <small>{{ cabinScoreLabel }} · {{ formatSnapshotTime(cabinSnapshot?.updated_at) }}</small>
                </div>
              </section>

              <section class="cabin-info-layout">
                <div class="readout-grid cabin-readouts">
                  <div class="readout-tile">
                    <span>CO2</span>
                    <strong>{{ cabinContext.co2_ppm }} ppm</strong>
                    <small>{{ co2Level }}</small>
                  </div>
                  <div class="readout-tile">
                    <span>温度</span>
                    <strong>{{ cabinContext.temperature_c }}°C</strong>
                    <small>{{ temperatureLevel }}</small>
                  </div>
                  <div class="readout-tile">
                    <span>湿度</span>
                    <strong>{{ cabinContext.humidity }}%</strong>
                  </div>
                  <div class="readout-tile">
                    <span>空气质量</span>
                    <strong>{{ cabinContext.air_quality }}</strong>
                  </div>
                  <div class="readout-tile">
                    <span>行驶状态</span>
                    <strong>{{ cabinContext.drive_mode }}</strong>
                  </div>
                  <div class="readout-tile">
                    <span>驾驶员状态</span>
                    <strong>{{ cabinContext.driver_state }}</strong>
                  </div>
                </div>

                <article class="recommendation-card cabin-plan-card">
                  <div class="section-head">
                    <div>
                      <p class="section-eyebrow">Aroma Pilot</p>
                      <h3>一键智能香薰</h3>
                    </div>
                    <span class="section-note">{{ cabinRecommendation?.confidence ?? 82 }}% 匹配</span>
                  </div>
                  <p class="recommendation-summary">
                    {{ cabinRecommendation?.summary || '系统正在读取模拟传感器数据，并自动匹配场景、人设和时长。' }}
                  </p>
                  <div class="recommendation-pills">
                    <span class="meta-pill">{{ cabinRecommendation?.scene || selectedScene }}</span>
                    <span class="meta-pill">{{ cabinRecommendation?.persona || selectedPersona }}</span>
                    <span class="meta-pill">{{ cabinRecommendation?.duration_level || selectedDurationLevel }}</span>
                  </div>
                  <div class="tag-row">
                    <span
                      v-for="tag in cabinRecommendation?.environment_tags || ['模拟读取', '自动推荐']"
                      :key="tag"
                      class="sensor-tag"
                    >
                      {{ tag }}
                    </span>
                  </div>
                  <ul class="reason-list">
                    <li v-for="reason in cabinRecommendation?.reasons || ['正在等待车载模拟数据。']" :key="reason">
                      {{ reason }}
                    </li>
                  </ul>
                  <div class="smart-action-row">
                    <button type="button" class="mini-action" :disabled="cabinLoading || !canStart" @click="loadCabinSnapshot">
                      重新读取
                    </button>
                    <button type="button" class="primary-action smart-action" :disabled="!canStart || cabinLoading" @click="onSmartGenerate">
                      {{ cabinLoading ? '正在感知并生成…' : '一键智能生成并运行' }}
                    </button>
                  </div>
                  <p v-if="cabinMessage" class="feedback warn">{{ cabinMessage }}</p>
                </article>
              </section>
            </article>
          </aside>
        </section>

        <section v-else-if="isAuthenticated && isGenerating" class="generating-view soft-card" key="generating">
        <div class="generating-orbit">
          <div class="pulse pulse-outer" />
          <div class="pulse pulse-inner" />
          <div class="pulse-core" />
        </div>

        <div class="generating-copy">
          <p class="section-eyebrow">Composing</p>
          <h2>{{ selectedScene }}</h2>
          <p class="generating-hint">{{ generatingHint }}</p>
          <div class="generating-meta">
            <span class="meta-pill">{{ selectedPersona }}</span>
            <span class="meta-pill">{{ selectedDurationLevel }}</span>
          </div>
        </div>

        <div class="floating-note-row">
          <span class="floating-note">正在组织香气层次</span>
          <span class="floating-note">正在匹配角色语气</span>
          <span class="floating-note">正在生成结构化计划</span>
        </div>

        <div class="control-row centered">
          <button type="button" class="secondary-action danger" :disabled="!canStop" @click="onStop">
            取消本次生成
          </button>
        </div>
        </section>

        <section v-else-if="isAuthenticated" class="running-view" key="running">
        <article class="hero-card running-hero soft-card">
          <div class="hero-copy">
            <p class="hero-tag">{{ status?.mood_tag || currentSceneMeta.mood }}</p>
            <h2>{{ status?.plan_name || currentSceneMeta.title }}</h2>
            <p class="hero-desc">{{ status?.opening_line || currentSceneMeta.desc }}</p>
          </div>
          <div class="hero-mini-meta">
            <span class="meta-pill">{{ status?.scene || selectedScene }}</span>
            <span class="meta-pill">{{ status?.persona || selectedPersona }}</span>
            <span class="meta-pill">{{ status?.duration_level || selectedDurationLevel }}</span>
          </div>
        </article>

        <section class="running-grid">
          <article class="soft-card monitor-card main-monitor">
            <div class="monitor-top">
              <div>
                <p class="section-eyebrow">Current</p>
                <h3>{{ aromaLabel(status?.current_aroma ?? null) }}</h3>
              </div>
              <span class="live-dot" />
            </div>
            <div class="countdown-row">
              <div>
                <span class="metric-label">本段剩余</span>
                <strong>{{ formatMmSs(status?.segment_remaining_sec ?? 0) }}</strong>
              </div>
              <div>
                <span class="metric-label">总剩余</span>
                <strong>{{ formatMmSs(status?.total_remaining_sec ?? 0) }}</strong>
              </div>
            </div>
            <div class="progress-block">
              <div class="progress-text-row">
                <span>{{ progressText }}</span>
                <span>{{ status?.fan_speed ?? 0 }}%</span>
              </div>
              <progress class="progress-bar" max="100" :value="status?.fan_speed ?? 0" />
            </div>
          </article>

          <article class="soft-card monitor-card info-card">
            <p class="section-eyebrow">Runtime</p>
            <div class="info-list">
              <div class="info-item">
                <span class="metric-label">阶段</span>
                <strong>{{ phaseLabel[phase] ?? phase }}</strong>
              </div>
              <div class="info-item">
                <span class="metric-label">偏好映射</span>
                <strong>{{ status?.preference ?? '—' }}</strong>
              </div>
              <div class="info-item">
                <span class="metric-label">角色人格</span>
                <strong>{{ status?.persona ?? selectedPersona }}</strong>
              </div>
            </div>
          </article>
        </section>

        <article class="soft-card story-card">
          <div class="story-head">
            <div>
              <p class="section-eyebrow">Reason</p>
              <h3>香气理由</h3>
            </div>
            <span class="story-role">{{ status?.persona ?? selectedPersona }}</span>
          </div>
          <p class="story-main">{{ cleanedExplanation || '本次香氛说明会显示在这里。' }}</p>
          <div v-if="status?.closing_line" class="story-footer">
            <span class="story-divider" />
            <p class="story-closing">{{ status.closing_line }}</p>
          </div>
        </article>

        <div class="control-row">
          <button type="button" class="primary-action subtle" :disabled="!canPause" @click="onPause">暂停</button>
          <button type="button" class="primary-action subtle" :disabled="!canResume" @click="onResume">恢复</button>
          <button type="button" class="secondary-action danger" :disabled="!canStop" @click="onStop">终止</button>
        </div>
      </section>
      </Transition>

      <section v-if="persistentFeedback" class="feedback-panel soft-card">
        <p v-if="status?.error_message" class="feedback error">{{ persistentFeedback }}</p>
        <p v-else-if="wsError" class="feedback warn">{{ persistentFeedback }}</p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  --bg-main: #110f1c;
  --bg-top: #171124;
  --bg-bottom: #0b0913;
  --mist-highlight: rgba(255, 255, 255, 0.14);
  --mist-secondary: rgba(255, 255, 255, 0.1);
  --panel-bg: rgba(255, 255, 255, 0.12);
  --panel-border: rgba(255, 255, 255, 0.18);
  --text-main: #fffaf8;
  --text-soft: rgba(255, 250, 248, 0.74);
  --accent: #b89cff;
  --accent-soft: rgba(184, 156, 255, 0.22);
  --accent-strong: #dbcdfd;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  color: var(--text-main);
  background:
    radial-gradient(circle at 18% 16%, var(--mist-highlight), transparent 22%),
    radial-gradient(circle at 80% 12%, var(--mist-secondary), transparent 24%),
    linear-gradient(180deg, var(--bg-top) 0%, var(--bg-main) 58%, var(--bg-bottom) 100%);
  transition:
    background 0.8s ease,
    color 0.45s ease;
}

.theme-sleep {
  --bg-top: #221738;
  --bg-main: #120f22;
  --bg-bottom: #080611;
  --mist-highlight: rgba(233, 220, 255, 0.2);
  --mist-secondary: rgba(201, 177, 255, 0.12);
  --accent: #b79cf7;
  --accent-soft: rgba(183, 156, 247, 0.3);
  --accent-strong: #d8cdfa;
}

.theme-commute {
  --bg-top: #3a2318;
  --bg-main: #1f1611;
  --bg-bottom: #0d0907;
  --mist-highlight: rgba(255, 219, 180, 0.22);
  --mist-secondary: rgba(255, 194, 126, 0.14);
  --accent: #f2b46d;
  --accent-soft: rgba(242, 180, 109, 0.3);
  --accent-strong: #ffe0b8;
}

.theme-focus {
  --bg-top: #173127;
  --bg-main: #101d18;
  --bg-bottom: #090d0b;
  --mist-highlight: rgba(220, 255, 238, 0.16);
  --mist-secondary: rgba(149, 208, 182, 0.14);
  --accent: #95d0b6;
  --accent-soft: rgba(149, 208, 182, 0.26);
  --accent-strong: #d9f2e7;
}

.theme-meditation {
  --bg-top: #152438;
  --bg-main: #0f1621;
  --bg-bottom: #070b11;
  --mist-highlight: rgba(221, 236, 255, 0.18);
  --mist-secondary: rgba(145, 184, 234, 0.14);
  --accent: #91b8ea;
  --accent-soft: rgba(145, 184, 234, 0.28);
  --accent-strong: #d8e8fb;
}

.theme-morning {
  --bg-top: #3b211f;
  --bg-main: #211414;
  --bg-bottom: #0f0a0b;
  --mist-highlight: rgba(255, 231, 225, 0.2);
  --mist-secondary: rgba(244, 166, 162, 0.14);
  --accent: #f4a6a2;
  --accent-soft: rgba(244, 166, 162, 0.28);
  --accent-strong: #ffd7d3;
}

.mist {
  position: absolute;
  border-radius: 999px;
  filter: blur(60px);
  opacity: 0.48;
  pointer-events: none;
  animation: drift 14s ease-in-out infinite;
  transition:
    background 0.85s ease,
    opacity 0.6s ease,
    transform 0.8s ease;
}

.mist-1 {
  width: 260px;
  height: 260px;
  top: 32px;
  left: -30px;
  background: var(--accent-soft);
}

.mist-2 {
  width: 320px;
  height: 320px;
  top: 140px;
  right: -80px;
  background: var(--mist-highlight);
  animation-delay: -3s;
}

.mist-3 {
  width: 220px;
  height: 220px;
  bottom: 90px;
  left: 20%;
  background: color-mix(in srgb, var(--accent-soft) 70%, white 30%);
  animation-delay: -7s;
}

.app-frame {
  position: relative;
  z-index: 1;
  width: min(100%, 1540px);
  margin: 0 auto;
  padding: 1rem 1.1rem 2.2rem;
}

.brand-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.55rem;
}

.brand-mark,
.section-eyebrow,
.hero-tag,
.action-label {
  margin: 0;
  font-size: 0.74rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent-strong);
}

.brand-title {
  margin: 0.4rem 0 0;
  font-size: 1.55rem;
  font-weight: 700;
}

.phase-pill,
.meta-pill,
.section-note {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-main);
  backdrop-filter: blur(12px);
}

.phase-pill {
  white-space: nowrap;
}

.user-pill {
  color: var(--accent-strong);
}

.soft-card {
  position: relative;
  overflow: hidden;
  border-radius: 28px;
  border: 1px solid var(--panel-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.17), rgba(255, 255, 255, 0.08)),
    var(--panel-bg);
  backdrop-filter: blur(18px);
  box-shadow:
    0 18px 50px rgba(7, 5, 14, 0.28),
    0 0 0 1px rgba(255, 255, 255, 0.04) inset,
    0 0 42px color-mix(in srgb, var(--accent-soft) 45%, transparent 55%);
  transition:
    border-color 0.55s ease,
    box-shadow 0.7s ease,
    background 0.7s ease,
    transform 0.35s ease;
}

.soft-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.08), transparent 42%);
  pointer-events: none;
  transition: background 0.6s ease;
}


.idle-view,
.running-view {
  display: grid;
  gap: 1rem;
}

.idle-view {
  min-height: calc(100vh - 7.4rem);
  grid-template-columns: 84px minmax(560px, 1fr) minmax(460px, 0.82fr);
  align-items: stretch;
  transition: grid-template-columns 0.35s ease;
}

.idle-view:has(.history-sidebar.expanded) {
  grid-template-columns: 360px minmax(520px, 1fr) minmax(440px, 0.78fr);
}

.manual-panel {
  display: grid;
  gap: 1rem;
  min-width: 0;
  height: 100%;
}

.auth-view {
  min-height: 70vh;
  display: grid;
  grid-template-columns: 1fr 0.86fr;
  gap: 1.2rem;
  align-items: center;
  padding: 1.2rem;
}

.auth-copy {
  position: relative;
  z-index: 1;
}

.auth-copy h2 {
  margin: 0.55rem 0 0;
  font-size: 2rem;
  line-height: 1.12;
}

.auth-copy p {
  margin: 1rem 0 0;
  color: var(--text-soft);
  line-height: 1.8;
}

.auth-form {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 0.8rem;
  padding: 1rem;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.auth-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
}

.auth-tabs button,
.mini-action {
  min-height: 36px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-main);
}

.auth-tabs button.active {
  background: rgba(255, 255, 255, 0.18);
  color: var(--accent-strong);
}

.field-label {
  display: grid;
  gap: 0.35rem;
  color: var(--text-soft);
  font-size: 0.88rem;
}

.field-label input {
  min-height: 46px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(10, 9, 16, 0.36);
  color: var(--text-main);
  padding: 0 0.9rem;
  font-size: 1rem;
}

.hero-card {
  display: grid;
  grid-template-columns: 1.35fr 0.65fr;
  gap: 1rem;
  padding: 1.2rem;
  min-height: 240px;
}

.hero-copy {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.hero-copy h2 {
  margin: 0.45rem 0 0;
  font-size: 2rem;
  line-height: 1.05;
}

.hero-desc {
  margin: 0.8rem 0 0;
  font-size: 1rem;
  line-height: 1.7;
}

.hero-support {
  margin: 1rem 0 0;
  max-width: 34rem;
  color: var(--text-soft);
  line-height: 1.7;
}

.hero-orb,
.generating-orbit {
  display: flex;
  align-items: center;
  justify-content: center;
}

.hero-orb::before {
  content: '';
  width: 220px;
  height: 220px;
  border-radius: 999px;
  background:
    radial-gradient(circle at 35% 30%, rgba(255, 255, 255, 0.55), transparent 25%),
    radial-gradient(circle at 50% 50%, var(--accent-soft), transparent 58%),
    radial-gradient(circle at 50% 50%, rgba(255, 255, 255, 0.08), transparent 78%);
  box-shadow:
    inset 0 0 30px rgba(255, 255, 255, 0.16),
    0 0 44px color-mix(in srgb, var(--accent-soft) 65%, transparent 35%);
  animation: breathe 6.5s ease-in-out infinite;
  transition:
    background 0.75s ease,
    box-shadow 0.75s ease,
    transform 0.75s ease;
}

.composer-grid,
.running-grid {
  display: grid;
  gap: 1rem;
}

.composer-grid {
  grid-template-columns: 1.2fr 0.95fr;
}

.running-grid {
  grid-template-columns: 1.1fr 0.9fr;
}

.section-card,
.monitor-card,
.story-card,
.history-card,
.action-card,
.generating-view,
.feedback-panel {
  padding: 1rem;
}

.history-sidebar {
  position: sticky;
  top: 1rem;
  min-width: 0;
  height: 100%;
  min-height: calc(100vh - 7.4rem);
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 0.8rem;
}

.history-rail {
  width: 100%;
  min-height: 100%;
  padding: 0.9rem 0.55rem;
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 0.7rem;
  text-align: center;
  color: var(--text-main);
  cursor: pointer;
}

.history-sidebar.expanded .history-rail {
  min-height: 72px;
  grid-template-columns: auto 1fr auto;
  justify-items: start;
  align-content: center;
  padding: 0.85rem 1rem;
}

.history-sidebar.expanded .history-rail-text {
  writing-mode: horizontal-tb;
  letter-spacing: 0;
}

.history-rail-icon {
  position: relative;
  z-index: 1;
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: var(--accent-strong);
  font-size: 1.65rem;
  line-height: 1;
}

.history-rail-text {
  position: relative;
  z-index: 1;
  writing-mode: vertical-rl;
  letter-spacing: 0.18em;
  font-weight: 700;
  color: var(--text-main);
}

.history-rail small {
  position: relative;
  z-index: 1;
  min-width: 30px;
  min-height: 30px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-soft) 55%, transparent 45%);
  color: var(--text-soft);
}

.cabin-view {
  position: sticky;
  top: 1rem;
  min-width: 0;
  height: 100%;
  min-height: calc(100vh - 7.4rem);
}

.cabin-dashboard {
  min-height: 100%;
  padding: 1rem;
  display: grid;
  grid-template-rows: auto minmax(260px, 0.82fr) auto;
  gap: 1rem;
}

.cabin-topbar,
.cabin-top-actions {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: flex-start;
}

.cabin-topbar h2 {
  margin: 0.35rem 0 0;
  font-size: 1.75rem;
}

.cabin-top-actions {
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.cabin-stage {
  position: relative;
  z-index: 1;
  min-height: 280px;
  overflow: hidden;
  border-radius: 26px;
  border: 1px solid rgba(255, 255, 255, 0.13);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.04)),
    radial-gradient(circle at 50% 34%, color-mix(in srgb, var(--accent-soft) 74%, transparent 26%), transparent 42%);
}

.car-visual {
  position: absolute;
  left: 50%;
  top: 52%;
  width: min(105%, 560px);
  transform: translate(-50%, -50%);
}

.car-visual svg {
  width: 100%;
  overflow: visible;
}

.car-glow {
  position: absolute;
  inset: 16% 8% 0;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-soft) 52%, transparent 48%);
  filter: blur(42px);
  opacity: 0.75;
  animation: cabinPulse 4s ease-in-out infinite;
}

.car-body {
  fill: rgba(255, 255, 255, 0.13);
  stroke: rgba(255, 255, 255, 0.58);
  stroke-width: 4;
}

.car-window {
  fill: color-mix(in srgb, var(--accent-soft) 64%, rgba(255, 255, 255, 0.06) 36%);
  stroke: rgba(255, 255, 255, 0.32);
  stroke-width: 3;
}

.car-line,
.car-shadow {
  fill: none;
  stroke: color-mix(in srgb, var(--accent-strong) 78%, transparent 22%);
  stroke-width: 4;
  stroke-linecap: round;
}

.car-shadow {
  opacity: 0.35;
  stroke-width: 10;
}

.wheel {
  fill: rgba(10, 9, 16, 0.72);
  stroke: rgba(255, 255, 255, 0.48);
  stroke-width: 5;
}

.wheel-core {
  fill: var(--accent-strong);
  opacity: 0.82;
}

.cabin-mist {
  position: absolute;
  width: 140px;
  height: 58px;
  border-radius: 999px;
  background: radial-gradient(circle, var(--accent-soft), transparent 66%);
  filter: blur(12px);
  animation: cabinMist 5s ease-in-out infinite;
}

.cabin-mist-a {
  left: 29%;
  top: 34%;
}

.cabin-mist-b {
  right: 24%;
  top: 46%;
  animation-delay: -2s;
}

.airflow-field {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.airflow-field span {
  position: absolute;
  width: 210px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, var(--accent-strong), transparent);
  opacity: 0.64;
  animation: airflow 3.7s linear infinite;
}

.airflow-left span {
  left: -190px;
}

.airflow-right span {
  right: -190px;
  animation-name: airflowReverse;
}

.airflow-field span:nth-child(1) {
  top: 28%;
}

.airflow-field span:nth-child(2) {
  top: 48%;
  animation-delay: -1.1s;
}

.airflow-field span:nth-child(3) {
  top: 68%;
  animation-delay: -2.1s;
}

.cabin-score-panel {
  position: absolute;
  right: 1rem;
  top: 1rem;
  z-index: 2;
  min-width: 132px;
  padding: 0.9rem;
  border-radius: 22px;
  background: rgba(9, 8, 15, 0.38);
  border: 1px solid rgba(255, 255, 255, 0.14);
  backdrop-filter: blur(12px);
}

.cabin-score-panel span,
.cabin-score-panel small {
  display: block;
  color: var(--text-soft);
}

.cabin-score-panel strong {
  display: block;
  font-size: 2.3rem;
  line-height: 1.1;
}

.cabin-info-layout {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

.cabin-readouts {
  align-content: start;
}

.cabin-plan-card {
  padding: 1rem;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.readout-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
}

.readout-tile {
  min-height: 78px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.25rem;
  padding: 0.75rem;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.075);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.readout-tile span,
.readout-tile small {
  color: var(--text-soft);
  font-size: 0.78rem;
}

.readout-tile strong {
  font-size: 0.98rem;
}

.recommendation-card {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.recommendation-main {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 0.8rem;
}

.recommendation-summary {
  margin: 0;
  line-height: 1.75;
  color: var(--text-soft);
}

.recommendation-pills,
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.sensor-tag {
  position: relative;
  z-index: 1;
  min-height: 30px;
  padding: 0 0.75rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  background: color-mix(in srgb, var(--accent-soft) 62%, transparent 38%);
  color: var(--accent-strong);
  border: 1px solid rgba(255, 255, 255, 0.13);
  font-size: 0.82rem;
}

.reason-list {
  position: relative;
  z-index: 1;
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-soft);
  line-height: 1.68;
}

.reason-list li + li {
  margin-top: 0.45rem;
}

.smart-action-row {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 0.55fr 1fr;
  gap: 0.65rem;
}

.smart-action {
  width: 100%;
}

.story-head {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: flex-start;
  margin-bottom: 0.9rem;
}

.story-head h3 {
  margin: 0.35rem 0 0;
  font-size: 1.08rem;
}

.story-role {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  padding: 0 0.8rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: var(--text-soft);
  font-size: 0.82rem;
}

.section-head,
.monitor-top {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: flex-start;
  margin-bottom: 0.9rem;
}

.compact-head {
  margin-bottom: 0.7rem;
}

.section-head h3,
.monitor-top h3,
.action-card h3 {
  margin: 0.35rem 0 0;
  font-size: 1.1rem;
}

.scene-stack,
.persona-stack,
.duration-row,
.info-list,
.history-list {
  display: grid;
  gap: 0.7rem;
}

.scene-option,
.persona-option,
.duration-option,
.primary-action,
.secondary-action {
  position: relative;
  z-index: 1;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-main);
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.scene-option,
.persona-option {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  min-height: 94px;
  padding: 0.95rem;
  border-radius: 22px;
  text-align: left;
}

.duration-row {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.duration-option {
  min-height: 98px;
  padding: 0.8rem 0.65rem;
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.35rem;
  text-align: center;
}

.scene-option.active,
.persona-option.active,
.duration-option.active {
  border-color: rgba(255, 255, 255, 0.34);
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0.08));
  box-shadow: 0 12px 28px rgba(5, 4, 10, 0.16);
}

.scene-option-title,
.persona-title,
.duration-title {
  font-size: 1rem;
  font-weight: 700;
}

.scene-option-desc,
.persona-desc,
.duration-desc,
.persona-vibe,
.story-closing,
.feedback,
.section-note {
  color: var(--text-soft);
}

.persona-vibe {
  font-size: 0.8rem;
}

.action-card {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
}

.action-copy p {
  margin: 0.45rem 0 0;
  color: var(--text-soft);
}

.action-feedback,
.history-applied {
  color: var(--accent-strong) !important;
  font-weight: 700;
}

.primary-action,
.secondary-action {
  min-height: 54px;
  padding: 0 1.1rem;
  border-radius: 999px;
  font-size: 0.98rem;
  font-weight: 700;
}

.primary-action {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.92), var(--accent-strong));
  color: #120f1f;
  border-color: transparent;
}

.primary-action.subtle {
  background: rgba(255, 255, 255, 0.12);
  color: var(--text-main);
  border-color: rgba(255, 255, 255, 0.14);
}

.secondary-action.danger {
  border-color: rgba(255, 210, 210, 0.32);
}

.mini-action {
  position: relative;
  z-index: 1;
  padding: 0 0.85rem;
  font-size: 0.86rem;
}

.mini-action:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.danger-text {
  color: #ffd2d2;
}

.history-item {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.9rem;
  padding: 0.9rem;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.075);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.history-item strong {
  display: block;
  margin-top: 0.2rem;
  font-size: 1rem;
}

.history-item p,
.empty-history {
  margin: 0.35rem 0 0;
  color: var(--text-soft);
  line-height: 1.6;
}

.history-applied {
  font-size: 0.86rem;
}

.history-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.history-card {
  min-height: 0;
  overflow: auto;
}

.generating-view {
  min-height: 72vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  gap: 1.2rem;
}

.generating-orbit {
  position: relative;
  width: 220px;
  height: 220px;
}

.pulse,
.pulse-core {
  position: absolute;
  inset: 50%;
  transform: translate(-50%, -50%);
  border-radius: 999px;
}

.pulse-outer {
  width: 220px;
  height: 220px;
  background: radial-gradient(circle, var(--accent-soft), transparent 68%);
  animation: breathe 4.6s ease-in-out infinite;
}

.pulse-inner {
  width: 150px;
  height: 150px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(12px);
  animation: breathe 3.2s ease-in-out infinite;
}

.pulse-core {
  width: 64px;
  height: 64px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.94), var(--accent-strong));
  box-shadow: 0 0 40px var(--accent-soft);
}

.generating-copy h2 {
  margin: 0.45rem 0 0;
  font-size: 2rem;
}

.generating-hint {
  margin: 0.8rem 0 0;
  min-height: 3.4rem;
  font-size: 1rem;
  line-height: 1.7;
  color: var(--text-soft);
}

.generating-meta,
.floating-note-row,
.hero-mini-meta,
.control-row,
.countdown-row,
.progress-text-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.floating-note-row {
  justify-content: center;
}

.floating-note {
  min-height: 34px;
  padding: 0 0.9rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.07);
  color: var(--text-soft);
}

.centered {
  justify-content: center;
}

.running-hero {
  grid-template-columns: 1fr;
  min-height: unset;
}

.hero-mini-meta {
  margin-top: 1rem;
}

.main-monitor h3 {
  font-size: 1.65rem;
}

.live-dot {
  width: 14px;
  height: 14px;
  border-radius: 999px;
  background: var(--accent-strong);
  box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.4);
  animation: ping 2.2s ease-out infinite;
}

.countdown-row {
  justify-content: space-between;
  margin-top: 0.9rem;
}

.metric-label {
  display: block;
  font-size: 0.76rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-soft);
  margin-bottom: 0.28rem;
}

.countdown-row strong,
.info-item strong {
  font-size: 1.25rem;
}

.progress-block {
  margin-top: 1rem;
}

.progress-text-row {
  justify-content: space-between;
  font-size: 0.92rem;
  color: var(--text-soft);
  margin-bottom: 0.45rem;
}

.progress-bar {
  width: 100%;
  height: 12px;
  accent-color: var(--accent);
}

.info-list {
  margin-top: 0.6rem;
}

.story-main {
  margin: 0;
  line-height: 1.95;
  font-size: 1.06rem;
  letter-spacing: 0.01em;
}

.story-footer {
  margin-top: 1rem;
}

.story-divider {
  display: block;
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0));
}

.story-closing {
  margin: 0.85rem 0 0;
  line-height: 1.75;
  color: var(--text-soft);
  font-size: 0.95rem;
}

.control-row {
  justify-content: flex-start;
}

.feedback-panel {
  padding: 0.95rem 1rem;
}

.feedback {
  margin: 0;
  line-height: 1.65;
}

.feedback + .feedback {
  margin-top: 0.45rem;
}

.feedback.error {
  color: #ffd2d2;
}

.feedback.warn {
  color: #fce7b2;
}

.scene-option:disabled,
.persona-option:disabled,
.duration-option:disabled,
.primary-action:disabled,
.secondary-action:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.scene-option:not(:disabled):hover,
.persona-option:not(:disabled):hover,
.duration-option:not(:disabled):hover,
.primary-action:not(:disabled):hover,
.secondary-action:not(:disabled):hover {
  transform: translateY(-1px);
}

@keyframes drift {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(10px, -14px, 0) scale(1.06);
  }
}

@keyframes breathe {
  0%,
  100% {
    transform: translate(-50%, -50%) scale(0.96);
    opacity: 0.78;
  }
  50% {
    transform: translate(-50%, -50%) scale(1.04);
    opacity: 1;
  }
}

@keyframes ping {
  0% {
    box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.35);
  }
  70% {
    box-shadow: 0 0 0 12px rgba(255, 255, 255, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(255, 255, 255, 0);
  }
}

@keyframes airflow {
  0% {
    transform: translateX(0) scaleX(0.55);
    opacity: 0;
  }
  18% {
    opacity: 0.68;
  }
  100% {
    transform: translateX(900px) scaleX(1.2);
    opacity: 0;
  }
}

@keyframes airflowReverse {
  0% {
    transform: translateX(0) scaleX(0.55);
    opacity: 0;
  }
  18% {
    opacity: 0.68;
  }
  100% {
    transform: translateX(-900px) scaleX(1.2);
    opacity: 0;
  }
}

@keyframes cabinPulse {
  0%,
  100% {
    opacity: 0.52;
    transform: scale(0.96);
  }
  50% {
    opacity: 0.9;
    transform: scale(1.04);
  }
}

@keyframes cabinMist {
  0%,
  100% {
    transform: translate3d(-10px, 0, 0);
    opacity: 0.32;
  }
  50% {
    transform: translate3d(16px, -8px, 0);
    opacity: 0.74;
  }
}

.view-fade-enter-active,
.view-fade-leave-active {
  transition:
    opacity 0.35s ease,
    transform 0.35s ease,
    filter 0.35s ease;
}

.view-fade-enter-from,
.view-fade-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.99);
  filter: blur(6px);
}

@media (max-width: 720px) {
  .brand-row,
  .section-head,
  .action-card,
  .cabin-topbar,
  .auth-view,
  .hero-card,
  .idle-view,
  .composer-grid,
  .running-grid,
  .cabin-info-layout,
  .countdown-row,
  .control-row {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-card,
  .idle-view,
  .composer-grid,
  .running-grid,
  .cabin-info-layout {
    min-height: 0;
    grid-template-columns: 1fr;
    display: grid;
  }

  .duration-row {
    grid-template-columns: 1fr;
  }

  .readout-grid,
  .smart-action-row {
    grid-template-columns: 1fr;
  }

  .cabin-view,
  .history-sidebar {
    position: static;
    min-height: 0;
    height: auto;
  }

  .history-rail {
    min-height: 72px;
    grid-template-columns: auto 1fr auto;
    align-content: center;
    justify-items: start;
    padding: 0.85rem 1rem;
  }

  .history-rail-text {
    writing-mode: horizontal-tb;
    letter-spacing: 0;
  }

  .history-card {
    position: static;
    max-height: none;
  }

  .cabin-stage {
    min-height: 250px;
  }

  .cabin-score-panel {
    left: 1rem;
    right: auto;
  }

  .car-visual {
    width: 118%;
    top: 58%;
  }

  .app-frame {
    padding: 0.95rem 0.85rem 2rem;
  }

  .hero-copy h2,
  .generating-copy h2 {
    font-size: 1.65rem;
  }

  .primary-action,
  .secondary-action {
    width: 100%;
  }

  .header-actions,
  .history-item,
  .history-actions {
    width: 100%;
  }

  .history-item,
  .history-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
