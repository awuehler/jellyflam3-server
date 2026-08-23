' Image-only flock stills cycle with optional crossfade. No Video / Sessions/Playing.

sub init()
  m.stillA = m.top.findNode("stillA")
  m.stillB = m.top.findNode("stillB")
  m.fadeToA = m.top.findNode("fadeToA")
  m.fadeToB = m.top.findNode("fadeToB")
  m.status = m.top.findNode("status")
  m.urls = []
  m.index = 0
  m.showingA = true
  m.busy = false
  m.fading = false
  m.pendingUri = ""

  m.reg = CreateObject("roRegistrySection", "JellyFlam3")
  applyJellyFlam3PackPresets(m.reg)
  m.baseUrl = m.reg.read("baseUrl")
  m.apiKey = m.reg.read("apiKey")
  m.userId = m.reg.read("userId")
  m.libraryId = m.reg.read("libraryId")
  m.fadeOn = registryBool(m.reg, "ssFade", true)
  m.dwellSec = registryInt(m.reg, "ssDwellSec", 12, 5, 120)
  m.fadeSec = registryFloat(m.reg, "ssFadeSec", 1.5, 0.3, 5.0)
  m.fadeToA.duration = m.fadeSec
  m.fadeToB.duration = m.fadeSec

  m.timer = CreateObject("roSGNode", "Timer")
  m.timer.repeat = true
  m.timer.duration = m.dwellSec
  m.timer.observeField("fire", "onTick")

  m.fadeToA.observeField("state", "onFadeState")
  m.fadeToB.observeField("state", "onFadeState")

  if m.baseUrl = invalid or m.baseUrl = "" or m.apiKey = invalid or m.apiKey = "" or m.userId = invalid or m.userId = "" or m.libraryId = invalid or m.libraryId = ""
    m.status.text = "No Jellyfin registry — sideload on furnace Pi or configure VoD Settings first"
    return
  end if

  m.status.text = "Loading flock stills…"
  m.task = CreateObject("roSGNode", "StillsTask")
  m.task.observeField("resultJson", "onList")
  m.task.baseUrl = m.baseUrl
  m.task.apiKey = m.apiKey
  m.task.userId = m.userId
  m.task.libraryId = m.libraryId
  m.task.control = "RUN"
end sub

function registryBool(reg as object, key as string, defaultVal as boolean) as boolean
  raw = reg.read(key)
  if raw = invalid or raw = "" then return defaultVal
  low = LCase(raw)
  if low = "true" or low = "1" or low = "yes" or low = "on" then return true
  if low = "false" or low = "0" or low = "no" or low = "off" then return false
  return defaultVal
end function

function registryInt(reg as object, key as string, defaultVal as integer, minVal as integer, maxVal as integer) as integer
  raw = reg.read(key)
  if raw = invalid or raw = "" then return defaultVal
  n = raw.toInt()
  if n < minVal then return minVal
  if n > maxVal then return maxVal
  return n
end function

function registryFloat(reg as object, key as string, defaultVal as float, minVal as float, maxVal as float) as float
  raw = reg.read(key)
  if raw = invalid or raw = "" then return defaultVal
  n = Val(raw)
  if n < minVal then return minVal
  if n > maxVal then return maxVal
  return n
end function

sub onList()
  raw = m.task.resultJson
  if raw = invalid or raw = ""
    m.status.text = "No stills (empty response)"
    return
  end if
  data = ParseJson(raw)
  if data = invalid or data.urls = invalid or data.urls.count() = 0
    reason = "No Primary images in library"
    if data <> invalid and data.error <> invalid then reason = data.error
    m.status.text = reason
    return
  end if
  m.urls = data.urls
  m.index = 0
  m.status.text = ""
  m.showingA = true
  m.stillA.opacity = 1.0
  m.stillB.opacity = 0.0
  m.stillA.uri = m.urls[0]
  m.timer.control = "start"
end sub

sub onTick()
  if m.urls = invalid or m.urls.count() = 0 then return
  if m.busy then return
  m.index = m.index + 1
  if m.index >= m.urls.count() then m.index = 0
  nextUri = m.urls[m.index]
  if not m.fadeOn
    hardCut(nextUri)
    return
  end if
  startCrossfade(nextUri)
end sub

sub hardCut(uri as string)
  if m.showingA
    m.stillA.uri = uri
    m.stillA.opacity = 1.0
    m.stillB.opacity = 0.0
  else
    m.stillB.uri = uri
    m.stillB.opacity = 1.0
    m.stillA.opacity = 0.0
  end if
end sub

sub startCrossfade(uri as string)
  m.busy = true
  m.pendingUri = uri
  if m.showingA
    m.stillB.unobserveField("loadStatus")
    m.stillB.observeField("loadStatus", "onIncomingLoaded")
    m.stillB.uri = uri
    ' Already cached / ready
    if m.stillB.loadStatus = "ready" or m.stillB.loadStatus = "loaded"
      onIncomingLoaded()
    end if
  else
    m.stillA.unobserveField("loadStatus")
    m.stillA.observeField("loadStatus", "onIncomingLoaded")
    m.stillA.uri = uri
    if m.stillA.loadStatus = "ready" or m.stillA.loadStatus = "loaded"
      onIncomingLoaded()
    end if
  end if
end sub

sub onIncomingLoaded()
  if not m.busy then return
  if m.fading then return
  if m.showingA
    status = m.stillB.loadStatus
  else
    status = m.stillA.loadStatus
  end if
  if status = "loading" or status = "none" then return
  if status = "failed" or status = "error"
    m.busy = false
    m.pendingUri = ""
    return
  end if
  ' ready / loaded — start fade (ignore spurious stopped while still loading)
  m.fading = true
  if m.showingA
    m.stillB.unobserveField("loadStatus")
    m.fadeToB.control = "start"
  else
    m.stillA.unobserveField("loadStatus")
    m.fadeToA.control = "start"
  end if
end sub

sub onFadeState()
  if not m.fading then return
  if m.showingA
    state = m.fadeToB.state
  else
    state = m.fadeToA.state
  end if
  if state <> "stopped" then return
  m.fading = false
  m.showingA = not m.showingA
  m.busy = false
  m.pendingUri = ""
end sub
