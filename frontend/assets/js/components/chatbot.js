/** Floating DSVV complaint assistant shared by public, authentication, and app pages. */
import { request } from '../services/mockApi.js'

const STARTER_REPLIES = [
  'Raise a complaint',
  'How do I register a grievance?',
  'Which department handles water leakage?',
  'How do I upload a photo?',
  'How can I track my complaint?',
]
const SESSION_STORAGE_KEY = 'dsvv_chatbot_session'
const HINGLISH_MARKERS = new Set([
  'ab', 'apni', 'batao', 'chahiye', 'ka', 'kar', 'kaise', 'karo', 'karu',
  'kya', 'meri', 'mujhe', 'pani', 'paani', 'shikayat', 'hai', 'hain', 'iska',
])

let mounted = false

export function mountChatbot() {
  if (mounted || !document.body) return
  mounted = true

  const host = document.createElement('section')
  host.className = 'dsvv-chat'
  host.setAttribute('aria-label', 'DSVV AI Grievance Assistant')
  host.innerHTML = `
    <button class="dsvv-chat__launcher" type="button" aria-label="Open DSVV AI Grievance Assistant" aria-controls="dsvv-chat-panel" aria-expanded="false">
      <span aria-hidden="true">✦</span><span class="dsvv-chat__launcher-text">Ask DSVV</span>
    </button>
    <section class="dsvv-chat__panel" id="dsvv-chat-panel" role="dialog" aria-label="DSVV AI Grievance Assistant" hidden>
      <header class="dsvv-chat__header">
        <span class="dsvv-chat__mark" aria-hidden="true">✦</span>
        <span class="dsvv-chat__heading"><strong>DSVV AI Grievance Assistant</strong><small>Grievance support · Hindi, English & Hinglish</small></span>
        <button class="dsvv-chat__icon dsvv-chat__speech-toggle" type="button" data-chat-speech aria-pressed="false" aria-label="Enable spoken replies" title="Enable spoken replies">🔇</button>
        <button class="dsvv-chat__icon" type="button" data-chat-minimize aria-label="Minimize assistant">−</button>
        <button class="dsvv-chat__icon" type="button" data-chat-close aria-label="Close assistant">×</button>
      </header>
      <div class="dsvv-chat__messages" role="log" aria-live="polite" aria-relevant="additions text" aria-label="Chat messages"></div>
      <div class="dsvv-chat__typing" aria-live="polite" hidden><span></span><span></span><span></span><em>Assistant is typing…</em></div>
      <form class="dsvv-chat__form">
        <label class="dsvv-chat__sr" for="dsvv-chat-input">Your message</label>
        <textarea id="dsvv-chat-input" rows="1" maxlength="1200" placeholder="Ask in Hindi, English, or Hinglish…" required></textarea>
        <button class="dsvv-chat__mic" type="button" data-chat-mic aria-label="Speak your message" title="Speak your message">🎙</button>
        <button type="submit" aria-label="Send message">➤</button>
      </form>
      <p class="dsvv-chat__note" data-chat-voice-status aria-live="polite">Never share passwords, OTPs, or tokens here.</p>
    </section>`
  document.body.append(host)

  const launcher = host.querySelector('.dsvv-chat__launcher')
  const panel = host.querySelector('.dsvv-chat__panel')
  const messages = host.querySelector('.dsvv-chat__messages')
  const form = host.querySelector('form')
  const input = host.querySelector('textarea')
  const sendButton = form.querySelector('button')
  const micButton = host.querySelector('[data-chat-mic]')
  const speechButton = host.querySelector('[data-chat-speech]')
  const voiceStatus = host.querySelector('[data-chat-voice-status]')
  const typing = host.querySelector('.dsvv-chat__typing')
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  const speechSupported = typeof SpeechRecognition === 'function'
  const speechSynthesis = window.speechSynthesis
  const speechOutputSupported = Boolean(
    speechSynthesis && typeof speechSynthesis.speak === 'function'
      && typeof window.SpeechSynthesisUtterance === 'function',
  )
  let recognition = null
  let listening = false
  let finalTranscript = ''
  let speechRepliesEnabled = false
  let preferredLanguage = navigator.language?.toLowerCase().startsWith('hi') ? 'hi' : 'en'
  let busy = false
  let sessionId = readSessionId()

  if (!speechSupported) {
    micButton.disabled = true
    micButton.title = 'Speech recognition is not supported in this browser'
    micButton.setAttribute('aria-label', 'Speech recognition is not supported in this browser')
    voiceStatus.textContent = 'Voice input is not supported in this browser. You can still type your message.'
  } else {
    voiceStatus.textContent = "Voice recognition may use your browser's speech service. Never share passwords, OTPs, or tokens."
  }
  if (!speechOutputSupported) {
    speechButton.disabled = true
    speechButton.title = 'Spoken replies are not supported in this browser'
    speechButton.setAttribute('aria-label', 'Spoken replies are not supported in this browser')
  }

  function languageStyle(text) {
    if (/[\u0900-\u097f]/.test(text)) return 'hi'
    const words = (text.toLowerCase().match(/[a-z]+/g) || [])
    if (words.some((word) => HINGLISH_MARKERS.has(word))) return 'hinglish'
    return 'en'
  }

  function speechLocale(text = '') {
    const language = text ? languageStyle(text) : preferredLanguage
    return language === 'hi' ? 'hi-IN' : 'en-IN'
  }

  function speak(text, force = false) {
    if ((!speechRepliesEnabled && !force) || !speechOutputSupported || !text) return
    speechSynthesis.cancel()
    const utterance = new window.SpeechSynthesisUtterance(text)
    utterance.lang = speechLocale(text)
    speechSynthesis.speak(utterance)
  }

  function showVoiceError(error) {
    const messages = {
      'not-allowed': 'Microphone permission was denied. Allow microphone access in your browser settings, or type your message.',
      'service-not-allowed': 'The browser speech service is unavailable. You can still type your message.',
      'audio-capture': 'No microphone was found. Connect a microphone or type your message.',
      network: 'Speech recognition could not connect. Check your connection or type your message.',
      'no-speech': 'I did not hear anything. Please try again or type your message.',
      'language-not-supported': 'Speech recognition does not support this language setting in your browser. You can still type your message.',
    }
    voiceStatus.textContent = messages[error] || 'Voice input could not start. Check microphone permissions or type your message.'
  }

  function startListening() {
    if (!speechSupported || busy || listening) return
    try {
      recognition = new SpeechRecognition()
      recognition.lang = speechLocale(input.value)
      recognition.continuous = false
      recognition.interimResults = true
      recognition.maxAlternatives = 1
      finalTranscript = ''
      listening = true
      micButton.classList.add('is-listening')
      micButton.setAttribute('aria-label', 'Stop listening')
      micButton.title = 'Stop listening'
      voiceStatus.textContent = 'Listening… Speak in Hindi, English, or Hinglish.'

      recognition.onresult = (event) => {
        let interim = ''
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index]
          const transcript = result[0]?.transcript || ''
          if (result.isFinal) finalTranscript += transcript
          else interim += transcript
        }
        input.value = (finalTranscript + interim).trim()
      }
      recognition.onerror = (event) => showVoiceError(event.error)
      recognition.onend = () => {
        listening = false
        micButton.classList.remove('is-listening')
        micButton.setAttribute('aria-label', 'Speak your message')
        micButton.title = 'Speak your message'
        const transcript = finalTranscript.trim()
        if (transcript) {
          preferredLanguage = languageStyle(transcript)
          voiceStatus.textContent = ''
          send(transcript)
        }
      }
      recognition.start()
    } catch (error) {
      listening = false
      micButton.classList.remove('is-listening')
      micButton.setAttribute('aria-label', 'Speak your message')
      micButton.title = 'Speak your message'
      showVoiceError(error?.name === 'NotAllowedError' ? 'not-allowed' : '')
    }
  }

  function readSessionId() {
    try {
      return sessionStorage.getItem(SESSION_STORAGE_KEY) || ''
    } catch {
      return ''
    }
  }

  function rememberSession(id) {
    sessionId = id
    try {
      sessionStorage.setItem(SESSION_STORAGE_KEY, id)
    } catch {
      // The current page can still continue the chat without browser storage.
    }
  }

  function setBusy(value) {
    busy = value
    typing.hidden = !value
    input.disabled = value
    sendButton.disabled = value
    micButton.disabled = value || !speechSupported
    host.querySelectorAll('.dsvv-chat__quick-replies button, .dsvv-chat__suggestions button, .dsvv-chat__retry')
      .forEach((button) => { button.disabled = value })
  }

  function actionForReply(reply) {
    const normalized = reply.trim().toLowerCase()
    if (normalized === 'submit' || normalized === 'दर्ज करें') return 'submit'
    if (normalized === 'cancel' || normalized === 'रद्द करें') return 'cancel'
    if (normalized === 'edit' || normalized === 'बदलें' || normalized === 'विवरण बदलें') return 'edit'
    if (normalized === 'back' || normalized === 'पीछे') return 'back'
    if (normalized === 'continue' || normalized === 'जारी रखें') return 'continue'
    if (normalized === 'start new' || normalized === 'नई शुरू करें') return 'new'
    if (normalized === 'raise another complaint' || normalized === 'दूसरी शिकायत दर्ज करें') return 'new'
    if (normalized === 'raise a complaint' || normalized === 'शिकायत दर्ज करें' || normalized === 'नई शिकायत दर्ज') return 'raise_complaint'
    return ''
  }

  function disableExistingReplies() {
    host.querySelectorAll('.dsvv-chat__quick-replies button, .dsvv-chat__suggestions button')
      .forEach((button) => {
        button.disabled = true
        button.classList.add('is-disabled')
      })
  }

  function addQuickReplies(replies, className = 'dsvv-chat__quick-replies') {
    if (!Array.isArray(replies) || !replies.length) return
    const group = document.createElement('div')
    group.className = className
    group.setAttribute('aria-label', 'Suggested replies')
    replies.forEach((reply) => {
      if (typeof reply !== 'string' || !reply.trim()) return
      const button = document.createElement('button')
      button.type = 'button'
      button.textContent = reply
      button.addEventListener('click', () => {
        disableExistingReplies()
        send(reply, actionForReply(reply))
      })
      group.append(button)
    })
    if (group.childElementCount) messages.append(group)
  }

  function addMessage(text, role = 'assistant', options = {}) {
    const item = document.createElement('article')
    item.className = `dsvv-chat__message dsvv-chat__message--${role}`
    const bubble = document.createElement('div')
    bubble.className = 'dsvv-chat__bubble'
    bubble.textContent = text
    item.append(bubble)

    const meta = document.createElement('div')
    meta.className = 'dsvv-chat__meta'
    const time = document.createElement('time')
    const now = new Date()
    time.dateTime = now.toISOString()
    time.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    meta.append(time)
    if (options.source === 'ai' || options.sourceNotice) {
      const source = document.createElement('span')
      source.className = 'dsvv-chat__source'
      source.textContent = options.sourceNotice
        || (options.source === 'ai' ? 'AI assistant' : '')
      meta.append(source)
    }
    if (role === 'assistant' && speechOutputSupported) {
      const listenButton = document.createElement('button')
      listenButton.type = 'button'
      listenButton.className = 'dsvv-chat__speak'
      listenButton.textContent = 'Speak'
      listenButton.setAttribute('aria-label', 'Speak this reply aloud')
      listenButton.addEventListener('click', () => speak(text, true))
      meta.append(listenButton)
    }
    if (options.retry) {
      const retry = document.createElement('button')
      retry.type = 'button'
      retry.className = 'dsvv-chat__retry'
      retry.textContent = 'Retry'
      retry.addEventListener('click', () => send(options.retry, options.action || '', false))
      meta.append(retry)
    }
    item.append(meta)

    if (options.action?.href?.startsWith('/') && !options.action.href.startsWith('//') && options.action.label) {
      const link = document.createElement('a')
      link.className = 'dsvv-chat__action'
      link.href = options.action.href
      link.textContent = options.action.label
      item.append(link)
    }
    if (options.complaint?.timeline?.length) {
      const history = document.createElement('ul')
      history.className = 'dsvv-chat__timeline'
      options.complaint.timeline.slice(-4).forEach((event) => {
        const row = document.createElement('li')
        const label = document.createElement('span')
        label.textContent = event.label || 'Update'
        row.append(label)
        if (event.at) {
          const date = document.createElement('time')
          date.dateTime = event.at
          date.textContent = new Date(event.at).toLocaleString()
          row.append(date)
        }
        history.append(row)
      })
      item.append(history)
    }
    messages.append(item)
    if (options.quickReplies) addQuickReplies(options.quickReplies)
    messages.scrollTop = messages.scrollHeight
    return item
  }

  async function send(text, action = '', showUser = true) {
    const question = text.trim()
    if (!question || busy) return
    disableExistingReplies()
    if (showUser) addMessage(question, 'user')
    setBusy(true)

    try {
      const result = await request('/chatbot/message', {
        method: 'POST',
        body: { message: question, sessionId: sessionId || undefined, action: action || undefined },
        includeStatus: true,
      })
      const { data, status } = result
      if (!data || typeof data.reply !== 'string' || typeof data.sessionId !== 'string') {
        throw new Error('The assistant returned an incomplete response. Please retry.')
      }
      rememberSession(data.sessionId)
      if (data.step && data.step !== 'idle') {
        host.querySelectorAll('.dsvv-chat__suggestions').forEach((el) => el.remove())
      }
      if (data.step === 'done') {
        const reference = data.complaint?.reference || data.complaint?.id
        if (!reference || (data.created ? status !== 201 : status !== 200)) {
          throw new Error('The complaint could not be confirmed. Please retry to check its status.')
        }
      }
      addMessage(data.reply, 'assistant', data)
      if (showUser) preferredLanguage = languageStyle(question)
      speak(data.reply)
      input.value = ''
    } catch (error) {
      if (!input.value) input.value = question
      const message = error?.message || 'I could not connect just now. Please try again.'
      addMessage(message, 'assistant', { retry: question, action })
    } finally {
      setBusy(false)
      if (!panel.hidden) input.focus()
    }
  }

  function open() {
    panel.hidden = false
    launcher.setAttribute('aria-expanded', 'true')
    if (!messages.childElementCount) {
      addMessage('नमस्ते! मैं आपकी शिकायत में मदद के लिए यहाँ हूँ।\nHello! I can help you register, track, and understand a grievance.')
      addQuickReplies(STARTER_REPLIES, 'dsvv-chat__suggestions')
    }
    input.focus()
  }

  function close() {
    panel.hidden = true
    launcher.setAttribute('aria-expanded', 'false')
    launcher.focus()
  }

  launcher.addEventListener('click', () => panel.hidden ? open() : close())
  host.querySelector('[data-chat-close]').addEventListener('click', close)
  host.querySelector('[data-chat-minimize]').addEventListener('click', close)
  micButton.addEventListener('click', () => {
    if (listening) {
      recognition?.stop()
    } else {
      startListening()
    }
  })
  speechButton.addEventListener('click', () => {
    speechRepliesEnabled = !speechRepliesEnabled
    speechButton.setAttribute('aria-pressed', String(speechRepliesEnabled))
    speechButton.textContent = speechRepliesEnabled ? '🔊' : '🔇'
    speechButton.title = speechRepliesEnabled ? 'Disable spoken replies' : 'Enable spoken replies'
    speechButton.setAttribute('aria-label', speechButton.title)
    voiceStatus.textContent = speechRepliesEnabled
      ? 'Spoken replies enabled.'
      : 'Spoken replies disabled.'
    if (!speechRepliesEnabled && speechSynthesis) speechSynthesis.cancel()
  })
  form.addEventListener('submit', (event) => {
    event.preventDefault()
    send(input.value)
  })
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      form.requestSubmit()
    }
  })
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !panel.hidden) close()
  })
}
