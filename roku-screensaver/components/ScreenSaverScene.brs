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
  m.lastRepollSec = 0
  m.repolling = false
  m.handlingFail = false
  m.repollTask = invalid

  m.reg = CreateObject("roRegistrySection", "JellyFlam3")
  applyJellyFlam3PackPresets(m.reg)
  m.baseUrl = m.reg.read("baseUrl")
  m.apiKey = m.reg.read("apiKey")
  m.userId = m.reg.read("userId")
  m.libraryId = m.reg.read("libraryId")
  m.commercialMode = m.reg.read("commercialMode")
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
  m.stillA.observeField("loadStatus", "onStillALoad")
  m.stillB.observeField("loadStatus", "onStillBLoad")

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
  if m.commercialMode = invalid then m.commercialMode = ""
  m.task.commercialMode = m.commercialMode
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
    reason = "No Primary or Backdrop stills in library"
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

function flockRepollMinSec() as integer
  return 30
end function

function nowUnixSec() as integer
  dt = CreateObject("roDateTime")
  return dt.AsSeconds()
end function

sub dropUrl(uri as string)
  if uri = invalid or uri = "" then return
  if m.urls = invalid then m.urls = []
  kept = []
  for each u in m.urls
    if u <> uri then kept.push(u)
  end for
  m.urls = kept
  if m.index >= m.urls.count() then m.index = 0
end sub

sub maybeRepollStills()
  startStillsRepoll(false)
end sub

sub maybeWrapRefetchStills()
  startStillsRepoll(true)
end sub

sub startStillsRepoll(force as boolean)
  if m.repolling = true then return
  if force <> true
    now = nowUnixSec()
    if m.lastRepollSec <> invalid and m.lastRepollSec > 0 and (now - m.lastRepollSec) < flockRepollMinSec()
      return
    end if
    m.lastRepollSec = now
  end if
  m.repolling = true
  t = CreateObject("roSGNode", "StillsTask")
  t.observeField("resultJson", "onRepollList")
  t.baseUrl = m.baseUrl
  t.apiKey = m.apiKey
  t.userId = m.userId
  t.libraryId = m.libraryId
  if m.commercialMode = invalid then m.commercialMode = ""
  t.commercialMode = m.commercialMode
  t.control = "RUN"
  m.repollTask = t
end sub

sub onRepollList()
  m.repolling = false
  t = m.repollTask
  m.repollTask = invalid
  if t = invalid then return
  raw = t.resultJson
  if raw = invalid or raw = "" then return
  data = ParseJson(raw)
  if data = invalid or data.urls = invalid or data.urls.count() = 0 then return
  m.urls = data.urls
  if m.index >= m.urls.count() then m.index = 0
end sub

sub handleStillFailed(uri as string)
  if m.handlingFail = true then return
  if uri = invalid or uri = "" then return
  m.handlingFail = true
  dropUrl(uri)
  maybeRepollStills()
  m.busy = false
  m.fading = false
  m.pendingUri = ""
  if m.urls = invalid or m.urls.count() = 0
    if m.status <> invalid then m.status.text = "No stills left — flock empty or all 404"
    if m.timer <> invalid then m.timer.control = "stop"
    m.handlingFail = false
    return
  end if
  if m.index >= m.urls.count() then m.index = 0
  nextUri = m.urls[m.index]
  m.handlingFail = false
  if not m.fadeOn
    hardCut(nextUri)
  else
    startCrossfade(nextUri)
  end if
end sub

sub onStillALoad()
  handlePosterLoad(m.stillA, m.showingA = false)
end sub

sub onStillBLoad()
  handlePosterLoad(m.stillB, m.showingA = true)
end sub

sub handlePosterLoad(poster as object, incoming as boolean)
  if poster = invalid then return
  st = poster.loadStatus
  if st = "failed" or st = "error"
    handleStillFailed(poster.uri)
    return
  end if
  if incoming and m.busy and m.fading <> true
    if st = "ready" or st = "loaded"
      startIncomingFade()
    end if
  end if
end sub

sub startIncomingFade()
  if not m.busy then return
  if m.fading then return
  m.fading = true
  if m.showingA
    m.fadeToB.control = "start"
  else
    m.fadeToA.control = "start"
  end if
end sub

function shuffleCopy(src as object) as object
  bag = []
  if src = invalid then return bag
  for each u in src
    bag.push(u)
  end for
  n = bag.count()
  if n < 2 then return bag
  i = n - 1
  while i > 0
    j = Rnd(i + 1) - 1
    tmp = bag[i]
    bag[i] = bag[j]
    bag[j] = tmp
    i = i - 1
  end while
  return bag
end function

sub rotateUrlsPast(lastUri as string)
  if lastUri = invalid or lastUri = "" then return
  if m.urls = invalid or m.urls.count() < 2 then return
  n = m.urls.count()
  i = 0
  while i < n
    if m.urls[0] <> lastUri then return
    m.urls.push(m.urls.Shift())
    i = i + 1
  end while
end sub

sub onTick()
  if m.urls = invalid or m.urls.count() = 0 then return
  if m.busy then return
  m.index = m.index + 1
  if m.index >= m.urls.count()
    lastUri = m.urls[m.urls.count() - 1]
    if m.urls.count() > 1 then maybeWrapRefetchStills()
    m.urls = shuffleCopy(m.urls)
    rotateUrlsPast(lastUri)
    m.index = 0
  end if
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
    m.stillB.uri = uri
    if m.stillB.loadStatus = "ready" or m.stillB.loadStatus = "loaded"
      startIncomingFade()
    end if
  else
    m.stillA.uri = uri
    if m.stillA.loadStatus = "ready" or m.stillA.loadStatus = "loaded"
      startIncomingFade()
    end if
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
