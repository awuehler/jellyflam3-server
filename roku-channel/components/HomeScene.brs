sub init()
  m.title = m.top.findNode("title")
  m.status = m.top.findNode("status")
  m.rowList = m.top.findNode("rowList")
  m.spinner = m.top.findNode("spinner")
  m.settingsBtn = m.top.findNode("settingsBtn")
  m.retryBtn = m.top.findNode("retryBtn")
  m.detailTitle = m.top.findNode("detailTitle")
  m.detailMeta = m.top.findNode("detailMeta")
  m.detailDesc = m.top.findNode("detailDesc")
  m.chipDuration = m.top.findNode("chipDuration")
  m.chipGeneration = m.top.findNode("chipGeneration")
  m.chipLicense = m.top.findNode("chipLicense")
  m.chipPedigree = m.top.findNode("chipPedigree")
  m.flockCount = 0
  m.uiState = "loading"
  m.shuffleQueue = []
  m.currentPlayId = ""
  m.advancingClip = false

  m.rowList.observeField("rowItemSelected", "onRowItemSelected")
  m.rowList.observeField("rowItemFocused", "onRowItemFocused")
  m.rowList.observeField("requestSettings", "onRequestSettings")
  m.settingsBtn.observeField("buttonSelected", "onSettingsButton")
  if m.retryBtn <> invalid
    m.retryBtn.observeField("buttonSelected", "onRetryButton")
  end if

  m.registry = CreateObject("roRegistrySection", "JellyFlam3")
  clearDetailChrome()
  ensureDefaults()
  refreshFromRegistry()

  ' First-run: open settings when credentials are missing (* often never reaches Scene)
  if needsCredentials()
    openSettings()
  end if
end sub

' Distinct loading / empty / error / ready UX + focus-safe Retry.
function friendlyError(raw as string) as string
  if raw = invalid or raw = "" then return "Could not load flock — check Settings"
  msg = raw
  low = LCase(msg)
  if Instr(1, low, "timeout") > 0 or Instr(1, low, "cannot reach") > 0
    return "Network timeout — is the Pi Jellyfin URL reachable from this Roku?"
  else if Instr(1, low, "apiKey") > 0 or Instr(1, low, "401") > 0 or Instr(1, low, "unauthorized") > 0
    return "Auth failed — check apiKey in Settings"
  else if Instr(1, low, "userId") > 0
    return "Missing userId — set it in Settings"
  else if Instr(1, low, "baseurl") > 0
    return "Missing baseUrl — set Jellyfin URL in Settings"
  end if
  if Len(msg) > 140 then msg = Left(msg, 137) + "…"
  return msg
end function

sub setUiState(state as string, message as string)
  m.uiState = state
  showRetry = (state = "error" or state = "empty")
  if m.retryBtn <> invalid
    m.retryBtn.visible = showRetry
    m.retryBtn.focusable = showRetry
  end if
  if m.spinner <> invalid
    m.spinner.visible = (state = "loading")
  end if
  if m.rowList <> invalid
    m.rowList.visible = (state = "ready")
    m.rowList.focusable = (state = "ready")
  end if
  if m.status <> invalid and message <> invalid
    m.status.text = message
  end if
end sub

sub focusRecoveryControl()
  if m.retryBtn <> invalid and m.retryBtn.visible = true
    m.retryBtn.setFocus(true)
  else if m.settingsBtn <> invalid
    m.settingsBtn.setFocus(true)
  end if
end sub

sub onRetryButton()
  refreshFromRegistry()
end sub

sub clearDetailChrome()
  if m.detailTitle <> invalid then m.detailTitle.text = "Select a dream"
  if m.detailMeta <> invalid then m.detailMeta.text = ""
  if m.detailDesc <> invalid then m.detailDesc.text = ""
  if m.chipDuration <> invalid then m.chipDuration.text = ""
  if m.chipGeneration <> invalid then m.chipGeneration.text = ""
  if m.chipLicense <> invalid then m.chipLicense.text = ""
  if m.chipPedigree <> invalid then m.chipPedigree.text = ""
end sub

function firstOverviewLine(desc as string) as string
  if desc = invalid or desc = "" then return ""
  line = desc
  nl = Instr(1, line, Chr(10))
  if nl > 0 then line = Left(line, nl - 1)
  line = line.Trim()
  if Len(line) > 120 then line = Left(line, 117) + "…"
  return line
end function

sub updateDetailChrome(item as object)
  if item = invalid
    clearDetailChrome()
    return
  end if

  name = "Untitled"
  if item.title <> invalid and item.title <> "" then name = item.title
  if m.detailTitle <> invalid then m.detailTitle.text = name

  meta = ""
  if item.metaLine <> invalid then meta = item.metaLine
  if m.detailMeta <> invalid then m.detailMeta.text = meta

  if m.chipDuration <> invalid
    if item.durationLabel <> invalid and item.durationLabel <> ""
      m.chipDuration.text = item.durationLabel
    else if item.length <> invalid and item.length > 0
      m.chipDuration.text = item.length.toStr() + "s"
    else
      m.chipDuration.text = ""
    end if
  end if

  if m.chipGeneration <> invalid
    if item.generation <> invalid and item.generation <> ""
      m.chipGeneration.text = "Gen " + item.generation
    else
      m.chipGeneration.text = ""
    end if
  end if

  if m.chipLicense <> invalid
    if item.license <> invalid and item.license <> ""
      m.chipLicense.text = item.license
    else
      m.chipLicense.text = ""
    end if
  end if

  if m.chipPedigree <> invalid
    if item.pedigree <> invalid and item.pedigree <> ""
      m.chipPedigree.text = item.pedigree
    else
      m.chipPedigree.text = ""
    end if
  end if

  desc = ""
  if item.description <> invalid then desc = firstOverviewLine(item.description)
  if m.detailDesc <> invalid then m.detailDesc.text = desc
end sub

function needsCredentials() as boolean
  apiKey = m.registry.read("apiKey")
  userId = m.registry.read("userId")
  if apiKey = invalid or apiKey = "" then return true
  if userId = invalid or userId = "" then return true
  return false
end function

sub ensureDefaults()
  applyJellyFlam3PackPresets(m.registry)
  if m.registry.read("baseUrl") = invalid or m.registry.read("baseUrl") = ""
    m.registry.write("baseUrl", "http://192.168.X.Y:8096")
  end if
  if m.registry.read("commercialMode") = invalid
    m.registry.write("commercialMode", "false")
  end if
  ' Ambient loop defaults to Static MP4; set "hls" to compare remux re-loop.
  ' Reject anything other than mp4|hls.
  sm = m.registry.read("streamMode")
  if sm = invalid then sm = ""
  sm = LCase(sm.Trim())
  if sm <> "mp4" and sm <> "hls"
    m.registry.write("streamMode", "mp4")
  end if
  if m.registry.read("shuffleFlock") = invalid
    m.registry.write("shuffleFlock", "true")
  end if
  m.registry.flush()
end sub

function shuffleFlockEnabled() as boolean
  v = m.registry.read("shuffleFlock")
  if v = invalid then return false
  tl = LCase(v.Trim())
  return (tl = "true" or tl = "1" or tl = "yes")
end function

' Archive seed generations — continuous shuffle ignores misc/test/other.
function archiveGenerationAllowlist() as object
  return {
    "247": true
    "245": true
    "244": true
    "243": true
    "242": true
    "198": true
    "191": true
    "169": true
    "165": true
  }
end function

function generationFromMediaPath(mediaPath as string) as string
  if mediaPath = invalid or mediaPath = "" then return ""
  low = LCase(mediaPath)
  marker = "/by-generation/"
  idx = Instr(1, low, marker)
  if idx <= 0
    marker = "\by-generation\"
    idx = Instr(1, low, marker)
  end if
  if idx <= 0 then return ""
  rest = Mid(low, idx + Len(marker))
  slash = Instr(1, rest, "/")
  if slash <= 0 then slash = Instr(1, rest, "\")
  if slash <= 1 then return ""
  return Mid(rest, 1, slash - 1)
end function

function isArchiveGenerationEligible(it as object) as boolean
  if it = invalid then return false
  allow = archiveGenerationAllowlist()
  mediaPath = ""
  if it.mediaPath <> invalid then mediaPath = it.mediaPath
  low = LCase(mediaPath)
  if Instr(1, low, "by-generation/misc") > 0 or Instr(1, low, "by-generation\misc") > 0 then return false
  if Instr(1, low, "by-generation/test") > 0 or Instr(1, low, "by-generation\test") > 0 then return false

  gen = ""
  if it.generation <> invalid and it.generation <> ""
    gen = it.generation
  end if
  if gen = ""
    gen = generationFromMediaPath(mediaPath)
  end if
  if gen = "" then return false
  if allow.DoesExist(gen) = true then return true
  return false
end function

function shuffleCopy(src as object) as object
  out = []
  if src = invalid then return out
  for each it in src
    out.push(it)
  end for
  n = out.count()
  if n < 2 then return out
  for i = n - 1 to 1 step -1
    ' Rnd(k) returns 1..k inclusive
    j = Rnd(i + 1) - 1
    tmp = out[i]
    out[i] = out[j]
    out[j] = tmp
  end for
  return out
end function

sub rebuildShuffleQueue(excludeId as string)
  eligible = []
  if m.items = invalid then m.items = []
  for each it in m.items
    if isArchiveGenerationEligible(it)
      if excludeId = invalid or excludeId = "" or it.id <> excludeId
        eligible.push(it)
      end if
    end if
  end for
  m.shuffleQueue = shuffleCopy(eligible)
end sub

function takeNextShuffleItem() as object
  if m.shuffleQueue = invalid then m.shuffleQueue = []
  if m.shuffleQueue.count() = 0
    rebuildShuffleQueue("")
  end if
  if m.shuffleQueue.count() = 0 then return invalid
  return m.shuffleQueue.Shift()
end function

function countArchiveEligible() as integer
  n = 0
  if m.items = invalid then return 0
  for each it in m.items
    if isArchiveGenerationEligible(it) then n = n + 1
  end for
  return n
end function

function shuffleAdvanceAllowed() as boolean
  if not shuffleFlockEnabled() then return false
  ' Need at least two archive-gen sheep to make advance meaningful.
  return countArchiveEligible() > 1
end function

sub refreshFromRegistry()
  base = m.registry.read("baseUrl")
  if base = invalid then base = ""
  clearDetailChrome()
  if m.detailTitle <> invalid then m.detailTitle.text = "Loading flock…"
  if m.detailMeta <> invalid then m.detailMeta.text = base
  if m.rowList <> invalid then m.rowList.content = invalid
  setUiState("loading", "Loading flock from " + base + "…")
  m.task = createObject("roSGNode", "JellyfinTask")
  m.task.observeField("resultJson", "onTaskResult")
  m.task.baseUrl = base
  m.task.apiKey = m.registry.read("apiKey")
  m.task.userId = m.registry.read("userId")
  m.task.libraryId = m.registry.read("libraryId")
  m.task.commercialMode = m.registry.read("commercialMode") = "true"
  m.task.command = "list"
  m.task.control = "RUN"
end sub

sub showErrorUi(raw as string)
  msg = friendlyError(raw)
  clearDetailChrome()
  if m.detailTitle <> invalid then m.detailTitle.text = "Could not load flock"
  if m.detailMeta <> invalid then m.detailMeta.text = msg
  if m.detailDesc <> invalid then m.detailDesc.text = "Press Retry or open Settings to fix credentials / URL"
  if m.rowList <> invalid then m.rowList.content = invalid
  m.flockCount = 0
  setUiState("error", msg)
  focusRecoveryControl()
end sub

sub showEmptyUi()
  clearDetailChrome()
  if m.detailTitle <> invalid then m.detailTitle.text = "Flock is empty"
  if m.detailMeta <> invalid then m.detailMeta.text = "No dreams in this library yet"
  if m.detailDesc <> invalid then m.detailDesc.text = "Seed the Pi inbox, check libraryId, or turn off commercialMode filter"
  if m.rowList <> invalid then m.rowList.content = invalid
  m.flockCount = 0
  setUiState("empty", "Empty flock — Retry after seeding, or open Settings")
  focusRecoveryControl()
end sub

sub onTaskResult()
  raw = m.task.resultJson
  res = invalid
  if raw <> invalid and raw <> ""
    res = ParseJson(raw)
  end if

  if m.settings <> invalid or m.player <> invalid
    if res = invalid or (res.error <> invalid and res.error <> "")
      err = "Jellyfin error — check Settings"
      if res <> invalid and res.error <> invalid then err = friendlyError(res.error)
      m.status.text = err
    else if res <> invalid and res.items <> invalid
      m.status.text = "Loaded " + res.items.count().toStr() + " — close Settings to browse"
    end if
    return
  end if

  if res = invalid
    showErrorUi("Empty response from Jellyfin task")
    return
  end if

  if res.error <> invalid and res.error <> ""
    showErrorUi(res.error)
    return
  end if

  if m.pendingDeepLink <> invalid and m.pendingDeepLink <> ""
    ' List result while a deep-link is outstanding: show list only.
    ' Dedicated deep-link task owns playback to avoid dual Video instances.
  end if

  if res.items = invalid then res.items = []
  m.items = res.items
  m.flockCount = res.items.count()
  if m.flockCount = 0
    showEmptyUi()
    return
  end if

  content = createObject("roSGNode", "ContentNode")
  row = content.createChild("ContentNode")
  row.title = "Flock"
  for each it in res.items
    child = row.createChild("ContentNode")
    bindFlockItemFields(child, it)
  end for
  m.rowList.content = content
  first = m.rowList.content.getChild(0).getChild(0)
  updateDetailChrome(first)
  setUiState("ready", m.flockCount.toStr() + " dreams in flock")
  if m.player = invalid then m.rowList.setFocus(true)
end sub

' Map task JSON fields onto ContentNode for FlockItem / focus chrome.
sub bindFlockItemFields(child as object, it as object)
  if child = invalid or it = invalid then return
  child.title = it.title
  child.description = it.description
  child.hdPosterUrl = it.hdPosterUrl
  child.id = it.id
  child.addField("jellyfinId", "string", false)
  child.jellyfinId = it.id
  child.addField("streamUrl", "string", false)
  child.streamUrl = it.url
  child.addField("hlsUrl", "string", false)
  if it.hlsUrl <> invalid then child.hlsUrl = it.hlsUrl else child.hlsUrl = it.url
  child.addField("mp4Url", "string", false)
  if it.mp4Url <> invalid then child.mp4Url = it.mp4Url else child.mp4Url = ""
  child.addField("streamFormat", "string", false)
  if it.streamFormat <> invalid and it.streamFormat <> ""
    child.streamFormat = it.streamFormat
  else
    child.streamFormat = "hls"
  end if
  if it.length <> invalid then child.length = it.length
  child.addField("durationLabel", "string", false)
  if it.durationLabel <> invalid then child.durationLabel = it.durationLabel else child.durationLabel = ""
  child.addField("generation", "string", false)
  if it.generation <> invalid then child.generation = it.generation else child.generation = ""
  child.addField("license", "string", false)
  if it.license <> invalid then child.license = it.license else child.license = ""
  child.addField("pedigree", "string", false)
  if it.pedigree <> invalid then child.pedigree = it.pedigree else child.pedigree = ""
  child.addField("sheepId", "string", false)
  if it.sheepId <> invalid then child.sheepId = it.sheepId else child.sheepId = ""
  child.addField("metaLine", "string", false)
  if it.metaLine <> invalid then child.metaLine = it.metaLine else child.metaLine = ""
  child.addField("mediaPath", "string", false)
  if it.mediaPath <> invalid then child.mediaPath = it.mediaPath else child.mediaPath = ""
end sub

sub onDeepLinkResult()
  if m.deepLinkTask = invalid then return
  raw = m.deepLinkTask.resultJson
  res = invalid
  if raw <> invalid and raw <> "" then res = ParseJson(raw)
  m.deepLinkTask = invalid
  if res = invalid or (res.error <> invalid and res.error <> "")
    err = "Deep link failed"
    if res <> invalid and res.error <> invalid then err = res.error
    showErrorUi(err)
    return
  end if
  if res.items = invalid or res.items.count() = 0
    showErrorUi("Deep link miss — item not found")
    return
  end if
  it = res.items[0]
  ' List path may have already started this id — still restart cleanly via playItem/stopPlayer
  m.pendingDeepLink = ""
  node = createObject("roSGNode", "ContentNode")
  bindFlockItemFields(node, it)
  setUiState("ready", "Playing deep link")
  if shuffleFlockEnabled()
    startId = ""
    if it.id <> invalid then startId = it.id
    rebuildShuffleQueue(startId)
  end if
  playItem(node)
end sub

sub onRowItemFocused()
  ' Drive detail panel from focused ContentNode fields.
  if m.rowList = invalid or m.rowList.content = invalid then return
  idx = m.rowList.rowItemFocused
  if idx = invalid or idx.count() < 2 then return
  row = m.rowList.content.getChild(idx[0])
  if row = invalid then return
  item = row.getChild(idx[1])
  updateDetailChrome(item)
  if m.status <> invalid and m.flockCount <> invalid
    m.status.text = m.flockCount.toStr() + " dreams in flock"
  end if
end sub

sub onRowItemSelected()
  idx = m.rowList.rowItemSelected
  row = m.rowList.content.getChild(idx[0])
  item = row.getChild(idx[1])
  if shuffleFlockEnabled()
    startId = ""
    if item <> invalid and item.jellyfinId <> invalid then startId = item.jellyfinId
    rebuildShuffleQueue(startId)
    if m.status <> invalid
      pool = countArchiveEligible()
      if pool > 1
        n = 0
        if m.shuffleQueue <> invalid then n = m.shuffleQueue.count()
        m.status.text = "Shuffle play (" + pool.toStr() + " archive gens; " + n.toStr() + " queued)"
      else if pool = 1
        m.status.text = "Shuffle on — only one archive-gen sheep; looping it"
      else
        m.status.text = "Shuffle on — no archive-gen sheep; looping this clip"
      end if
    end if
  end if
  playItem(item)
end sub

sub playItem(item as object)
  if item = invalid then return
  m.advancingClip = false
  stopPlayer()
  player = createObject("roSGNode", "PlayerScreen")
  m.top.appendChild(player)
  m.player = player
  player.observeField("close", "onPlayerClose")
  player.observeField("clipFinished", "onClipFinished")
  player.allowShuffleAdvance = shuffleAdvanceAllowed()
  hls = ""
  if item.hlsUrl <> invalid then hls = item.hlsUrl
  if hls = "" and item.streamUrl <> invalid then hls = item.streamUrl
  mp4 = ""
  if item.mp4Url <> invalid then mp4 = item.mp4Url
  playId = ""
  if item.jellyfinId <> invalid then playId = item.jellyfinId
  m.currentPlayId = playId
  player.callFunc("playSheep", {
    url: hls
    hlsUrl: hls
    mp4Url: mp4
    title: item.title
    length: item.length
    id: playId
  })
  player.setFocus(true)
end sub

sub playItemFromData(it as object)
  if it = invalid then return
  node = createObject("roSGNode", "ContentNode")
  bindFlockItemFields(node, it)
  playItem(node)
end sub

sub stopPlayer()
  if m.player = invalid then return
  m.player.callFunc("stopSheep")
  m.top.removeChild(m.player)
  m.player = invalid
end sub

sub onClipFinished()
  if m.player = invalid then return
  if m.player.clipFinished <> true then return
  if not shuffleAdvanceAllowed() then return
  if m.advancingClip = true then return
  m.advancingClip = true
  nextIt = takeNextShuffleItem()
  if nextIt = invalid
    stopPlayer()
    if m.status <> invalid then m.status.text = "Shuffle queue empty"
    if m.rowList <> invalid then m.rowList.setFocus(true)
    return
  end if
  if m.status <> invalid
    left = 0
    if m.shuffleQueue <> invalid then left = m.shuffleQueue.count()
    m.status.text = "Next shuffle (" + left.toStr() + " left in round)"
  end if
  playItemFromData(nextIt)
end sub

sub onPlayerClose()
  m.advancingClip = false
  m.shuffleQueue = []
  m.currentPlayId = ""
  stopPlayer()
  if m.rowList <> invalid then m.rowList.setFocus(true)
end sub

sub onRequestSettings()
  openSettings()
end sub

sub onSettingsButton()
  openSettings()
end sub

sub openSettings()
  if m.settings <> invalid then return
  if m.settingsBtn <> invalid then m.settingsBtn.focusable = false
  if m.retryBtn <> invalid then m.retryBtn.focusable = false
  if m.rowList <> invalid then m.rowList.focusable = false
  settings = createObject("roSGNode", "SettingsScreen")
  m.top.appendChild(settings)
  m.settings = settings
  settings.observeField("close", "onSettingsClose")
  settings.callFunc("openSettings")
end sub

sub onSettingsClose()
  saved = false
  if m.settings <> invalid and m.settings.saved = true then saved = true
  if m.settings <> invalid
    m.top.removeChild(m.settings)
    m.settings = invalid
  end if
  if m.settingsBtn <> invalid then m.settingsBtn.focusable = true
  if saved
    refreshFromRegistry()
  else if needsCredentials()
    focusRecoveryControl()
  else if m.uiState = "error" or m.uiState = "empty"
    focusRecoveryControl()
  else
    if m.rowList <> invalid
      m.rowList.focusable = true
      m.rowList.setFocus(true)
    end if
  end if
end sub

function handleDeepLink(args as object) as void
  if args = invalid then return
  cid = args.contentId
  if cid = invalid or cid = "" then cid = args.contentID
  if cid = invalid or cid = "" then return
  m.pendingDeepLink = cid
  setUiState("loading", "Deep link " + cid + "…")
  t = createObject("roSGNode", "JellyfinTask")
  t.observeField("resultJson", "onDeepLinkResult")
  t.baseUrl = m.registry.read("baseUrl")
  t.apiKey = m.registry.read("apiKey")
  t.userId = m.registry.read("userId")
  t.libraryId = m.registry.read("libraryId")
  t.commercialMode = m.registry.read("commercialMode") = "true"
  t.command = "item"
  t.itemId = cid
  t.control = "RUN"
  m.deepLinkTask = t
end function

function onKeyEvent(key as string, press as boolean) as boolean
  if not press then return false
  if key = "options" or key = "info" or key = "lit_asterisk"
    openSettings()
    return true
  end if
  if key = "replay" or key = "play"
    if m.uiState = "error" or m.uiState = "empty"
      refreshFromRegistry()
      return true
    end if
  end if
  return false
end function
