sub init()
  m.top.focusable = true
  m.fields = ["baseUrl", "apiKey", "userId", "libraryId", "commercialMode", "streamMode", "shuffleFlock", "titleMode"]
  m.rowIds = ["row_baseUrl", "row_apiKey", "row_userId", "row_libraryId", "row_commercialMode", "row_streamMode", "row_shuffleFlock", "row_titleMode", "row_probeDisplay", "row_save", "row_cancel"]
  m.values = {}
  m.idx = 0
  m.registry = CreateObject("roRegistrySection", "JellyFlam3")
  m.keyboard = invalid
  m.streamModeNotice = ""
  m.streamModeCorrected = false
  m.inputNotice = ""
  m.displaySummary = ""
  m.versionLabel = m.top.findNode("versionLabel")
  refreshVersionLabel()

  for each id in m.rowIds
    row = m.top.findNode(id)
    row.observeField("rowSelected", "onRowSelected")
    row.observeField("navKey", "onNavKey")
  end for
end sub

' Roku practice: show channel version from manifest via roAppInfo (not a hard-coded string).
function channelVersionString() as string
  info = CreateObject("roAppInfo")
  if info = invalid then return ""
  ver = info.GetVersion()
  if ver = invalid or ver = "" then return ""
  return ver
end function

sub refreshVersionLabel()
  ver = channelVersionString()
  if m.versionLabel = invalid then return
  if ver = ""
    m.versionLabel.text = ""
    return
  end if
  line = "Version " + ver
  info = CreateObject("roAppInfo")
  if info <> invalid and info.IsDev() = true
    line = line + " (sideload)"
  end if
  m.versionLabel.text = line
end sub

function fieldHint(name as string) as string
  if name = "baseUrl"
    return "Jellyfin URL reachable from this Roku (no trailing slash)"
  else if name = "apiKey"
    return "Jellyfin Dashboard -> API Keys"
  else if name = "userId"
    return "Jellyfin user GUID (required)"
  else if name = "libraryId"
    return "Sheep library ParentId (recommended)"
  else if name = "commercialMode"
    return "OK toggles true/false and saves; true=commercial flock (hide NC; keep CC BY / CC0 / PD); false=show all"
  else if name = "streamMode"
    return "OK toggles mp4/hls and saves; mp4=ambient Direct Play loop; hls=Jellyfin remux compare"
  else if name = "shuffleFlock"
    return "OK toggles true/false and saves; true rotates archive gens + pedigree + tuple (skip misc/test); launch still heals leftover false"
  else if name = "titleMode"
    return "OK toggles filename/alias and saves; alias uses Overview Alias: line; missing alias falls back to filename"
  else if name = "probeDisplay"
    return "OK=capture roDeviceInfo + POST per-screen profile to Pi :8791 (multi-Roku/Kodi safe; hint only)"
  else if name = "save"
    return "Save & Reload - persist settings and reload flock"
  else if name = "cancel"
    return "Return (accepted edits remain saved)"
  end if
  return ""
end function

function normalizeStreamMode(raw as string) as string
  v = LCase(raw.Trim())
  m.streamModeCorrected = false
  if v = "hls" then return "hls"
  if v = "mp4" then return "mp4"
  m.streamModeCorrected = true
  return "mp4"
end function

function isValidStreamMode(raw as string) as boolean
  if raw = invalid then return false
  v = LCase(raw.Trim())
  return (v = "mp4" or v = "hls")
end function

function normalizeBool(raw as string, defaultVal as boolean) as string
  if raw = invalid then raw = ""
  tl = LCase(raw.Trim())
  if tl = "true" or tl = "1" or tl = "yes"
    return "true"
  else if tl = "false" or tl = "0" or tl = "no"
    return "false"
  end if
  if defaultVal = true then return "true"
  return "false"
end function

function isValidBoolToken(raw as string) as boolean
  if raw = invalid then return false
  tl = LCase(raw.Trim())
  return (tl = "true" or tl = "false" or tl = "1" or tl = "0" or tl = "yes" or tl = "no")
end function

function shuffleFlockDefault() as boolean
  return true
end function

function normalizeTitleMode(raw as string) as string
  if raw = invalid then return "filename"
  v = LCase(raw.Trim())
  if v = "alias" then return "alias"
  if v = "filename" then return "filename"
  return ""
end function

function isValidTitleMode(raw as string) as boolean
  v = normalizeTitleMode(raw)
  return (v = "filename" or v = "alias")
end function

function isValidBaseUrl(raw as string) as boolean
  if raw = invalid then return true
  s = raw.Trim()
  if s = "" then return true
  v = LCase(s)
  if Left(v, 8) <> "https://" and Left(v, 7) <> "http://" then return false
  return Len(s) > 10
end function

function isHexDashId(raw as string) as boolean
  if raw = invalid then return false
  s = LCase(raw.Trim())
  if s = "" then return true
  if Len(s) < 8 then return false
  hex = "0123456789abcdef-"
  i = 1
  while i <= Len(s)
    if Instr(1, hex, Mid(s, i, 1)) = 0 then return false
    i = i + 1
  end while
  return true
end function

function isValidApiKey(raw as string) as boolean
  if raw = invalid then return true
  s = raw.Trim()
  if s = "" then return true
  if Instr(1, s, " ") > 0 then return false
  return Len(s) >= 8
end function

function applyEditedValue(name as string, text as string) as boolean
  if text = invalid then text = ""
  text = text.Trim()
  m.inputNotice = ""
  m.streamModeNotice = ""
  m.streamModeCorrected = false
  if name = "streamMode"
    if isValidStreamMode(text) <> true
      m.inputNotice = "streamMode invalid (" + text + ") - use mp4 or hls"
      return false
    end if
    m.values[name] = LCase(text)
    return true
  else if name = "commercialMode"
    if isValidBoolToken(text) <> true
      m.inputNotice = "commercialMode invalid (" + text + ") - use true or false"
      return false
    end if
    m.values[name] = normalizeBool(text, false)
    return true
  else if name = "shuffleFlock"
    if isValidBoolToken(text) <> true
      m.inputNotice = "shuffleFlock invalid (" + text + ") - use true or false"
      return false
    end if
    m.values[name] = normalizeBool(text, true)
    return true
  else if name = "titleMode"
    if isValidTitleMode(text) <> true
      m.inputNotice = "titleMode invalid (" + text + ") - use filename or alias"
      return false
    end if
    m.values[name] = normalizeTitleMode(text)
    return true
  else if name = "baseUrl"
    if isValidBaseUrl(text) <> true
      m.inputNotice = "baseUrl invalid - use http:// or https:// host (no trailing slash)"
      return false
    end if
    m.values[name] = text
    return true
  else if name = "apiKey"
    if isValidApiKey(text) <> true
      m.inputNotice = "apiKey invalid - paste the Jellyfin key (no spaces)"
      return false
    end if
    m.values[name] = text
    return true
  else if name = "userId" or name = "libraryId"
    if isHexDashId(text) <> true
      m.inputNotice = name + " invalid - use a Jellyfin GUID"
      return false
    end if
    m.values[name] = text
    return true
  end if
  m.values[name] = text
  return true
end function

function flagStr(v) as string
  if v = invalid then return "false"
  if v = true then return "true"
  if v = false then return "false"
  s = v.toStr()
  if s = "1" or LCase(s) = "true" then return "true"
  return "false"
end function

function readDisplaySummary() as string
  s = m.registry.read("displaySummary")
  if s = invalid then s = ""
  return s
end function

sub refreshProbeRowLabel()
  summary = m.displaySummary
  if summary = invalid or summary = ""
    summary = readDisplaySummary()
  end if
  if summary = invalid or summary = ""
    m.top.findNode("row_probeDisplay").label = "Fetch TV display (not captured yet)"
  else
    m.top.findNode("row_probeDisplay").label = "Fetch TV display: " + summary
  end if
end sub

sub openSettings()
  m.streamModeNotice = ""
  m.inputNotice = ""
  m.displaySummary = readDisplaySummary()
  refreshVersionLabel()
  for each name in m.fields
    val = m.registry.read(name)
    if val = invalid then val = ""
    if name = "streamMode"
      val = normalizeStreamMode(val)
      if m.streamModeCorrected = true
        m.streamModeNotice = "streamMode was invalid - using mp4"
      end if
    else if name = "commercialMode"
      val = normalizeBool(val, false)
    else if name = "shuffleFlock"
      val = normalizeBool(val, true)
    else if name = "titleMode"
      val = normalizeTitleMode(val)
      if val = "" then val = "filename"
    end if
    m.values[name] = val
    refreshRowLabel(name)
  end for
  m.top.findNode("row_save").label = "Save & Reload"
  m.top.findNode("row_cancel").label = "Back"
  refreshProbeRowLabel()
  focusIndex(0)
end sub

sub refreshRowLabel(name as string)
  val = m.values[name]
  if val = invalid then val = ""
  shown = val
  if name = "apiKey" and val <> "" and Len(val) > 4
    shown = Left(val, 2) + "..." + Right(val, 2) + " (" + Len(val).toStr() + " chars)"
  else if name = "streamMode"
    if val = "" then val = "mp4"
    shown = val
  else if name = "commercialMode"
    if val = "" then shown = "false"
  else if name = "shuffleFlock"
    if val = "" then shown = "true"
  else if name = "titleMode"
    if val = "" then shown = "filename"
  else if val = ""
    shown = "(empty)"
  end if
  m.top.findNode("row_" + name).label = name + ": " + shown
end sub

sub updateFooter()
  id = m.rowIds[m.idx]
  name = id
  if Left(id, 4) = "row_" then name = Mid(id, 5)
  hint = fieldHint(name)
  ' NOTE: do not name a local "pos" - Pos() is a reserved BrightScript builtin (&h9d).
  slot = "(" + (m.idx + 1).toStr() + "/" + m.rowIds.count().toStr() + ")"
  line = "Focus: " + name
  if hint <> "" then line = line + " - " + hint
  line = line + "  " + slot
  if m.streamModeNotice <> "" and name = "streamMode"
    line = line + " | " + m.streamModeNotice
  end if
  if m.inputNotice <> "" and isOkToggleField(name) <> true
    line = line + " | " + m.inputNotice
  end if
  if name = "probeDisplay" and m.displaySummary <> ""
    line = line + " | " + m.displaySummary
  end if
  m.top.findNode("footer").text = line
end sub

sub focusIndex(i as integer)
  if i < 0 then i = 0
  if i >= m.rowIds.count() then i = m.rowIds.count() - 1
  m.idx = i
  for fi = 0 to m.rowIds.count() - 1
    row = m.top.findNode(m.rowIds[fi])
    row.callFunc("setActive", fi = i)
  end for
  row = m.top.findNode(m.rowIds[i])
  row.setFocus(true)
  updateFooter()
end sub

sub onNavKey()
  if m.keyboard <> invalid then return
  key = ""
  for each id in m.rowIds
    row = m.top.findNode(id)
    if row.isInFocusChain()
      key = row.navKey
      exit for
    end if
  end for
  if key = "" then return
  if key = "down" or key = "right"
    focusIndex(m.idx + 1)
  else if key = "up" or key = "left"
    focusIndex(m.idx - 1)
  end if
end sub

sub onRowSelected()
  if m.keyboard <> invalid then return
  id = m.rowIds[m.idx]
  if id = "row_save"
    saveAndClose()
    return
  else if id = "row_cancel"
    m.top.close = true
    return
  else if id = "row_probeDisplay"
    probeAndSaveDisplay()
    return
  end if
  name = Mid(id, 5) ' strip "row_"
  if isOkToggleField(name)
    toggleChoice(name)
    return
  end if
  editField(name)
end sub

function isOkToggleField(name as string) as boolean
  return name = "commercialMode" or name = "streamMode" or name = "shuffleFlock" or name = "titleMode"
end function

function nextToggleValue(name as string) as string
  cur = ""
  if m.values <> invalid and m.values[name] <> invalid then cur = m.values[name]
  cur = LCase(cur.Trim())
  if name = "titleMode"
    if cur = "alias" then return "filename"
    return "alias"
  else if name = "streamMode"
    if cur = "hls" then return "mp4"
    return "hls"
  else if name = "commercialMode"
    if cur = "true" then return "false"
    return "true"
  else if name = "shuffleFlock"
    if cur = "false" then return "true"
    return "false"
  end if
  return cur
end function

sub toggleChoice(name as string)
  nextVal = nextToggleValue(name)
  if nextVal = invalid or nextVal = "" then return
  m.values[name] = nextVal
  m.registry.write(name, nextVal)
  m.registry.flush()
  m.top.saved = true
  m.inputNotice = ""
  refreshRowLabel(name)
  updateFooter()
end sub

function hostFromBaseUrl(base as string) as string
  if base = invalid or base = "" then return ""
  b = base.Trim()
  ' strip scheme
  idx = Instr(1, b, "://")
  if idx > 0 then b = Mid(b, idx + 3)
  ' strip path
  slash = Instr(1, b, "/")
  if slash > 0 then b = Left(b, slash - 1)
  ' strip port
  colon = Instr(1, b, ":")
  if colon > 0 then b = Left(b, colon - 1)
  return b
end function

function resolveDisplaySinkUrl() as string
  explicit = m.registry.read("displaySinkUrl")
  if explicit <> invalid and explicit <> ""
    u = explicit.Trim()
    while Len(u) > 0 and Right(u, 1) = "/"
      u = Left(u, Len(u) - 1)
    end while
    return u
  end if
  base = m.registry.read("baseUrl")
  if base = invalid then base = ""
  if m.values <> invalid and m.values["baseUrl"] <> invalid and m.values["baseUrl"] <> ""
    base = m.values["baseUrl"]
  end if
  host = hostFromBaseUrl(base)
  if host = "" then return ""
  return "http://" + host + ":8791"
end function

' roDeviceInfo -> registry, then POST per-screen profile to Pi sink.
sub probeAndSaveDisplay()
  di = CreateObject("roDeviceInfo")
  if di = invalid
    m.displaySummary = "probe failed (no roDeviceInfo)"
    refreshProbeRowLabel()
    updateFooter()
    return
  end if

  w = ""
  h = ""
  sz = di.GetDisplaySize()
  if sz <> invalid
    if sz.w <> invalid then w = sz.w.toStr()
    if sz.h <> invalid then h = sz.h.toStr()
  end if

  uiName = ""
  uiW = ""
  uiH = ""
  ui = di.GetUIResolution()
  if ui <> invalid
    if ui.name <> invalid then uiName = ui.name.toStr()
    if ui.width <> invalid then uiW = ui.width.toStr()
    if ui.height <> invalid then uiH = ui.height.toStr()
  end if

  videoMode = ""
  vm = di.GetVideoMode()
  if vm <> invalid then videoMode = vm.toStr()

  aspect = ""
  ar = di.GetDisplayAspectRatio()
  if ar <> invalid then aspect = ar.toStr()

  model = ""
  md = di.GetModel()
  if md <> invalid then model = md.toStr()
  modelName = ""
  mn = di.GetModelDisplayName()
  if mn <> invalid then modelName = mn.toStr()

  deviceId = ""
  cid = di.GetChannelClientId()
  if cid <> invalid and cid <> "" then deviceId = cid.toStr()
  if deviceId = "" and model <> "" then deviceId = "roku-" + model
  if deviceId = "" then deviceId = "roku-unknown"

  hdr10 = "false"
  hdr10Plus = "false"
  hlg = "false"
  dolbyVision = "false"
  hdrSeamless = "false"
  displayInternal = "false"
  props = di.GetDisplayProperties()
  if props <> invalid
    hdr10 = flagStr(props.Hdr10)
    if props.DoesExist("Hdr10Plus") then hdr10Plus = flagStr(props.Hdr10Plus)
    if props.DoesExist("HLG") then hlg = flagStr(props.HLG)
    if props.DoesExist("DolbyVision") then dolbyVision = flagStr(props.DolbyVision)
    if props.DoesExist("HdrSeamless") then hdrSeamless = flagStr(props.HdrSeamless)
    if props.DoesExist("Internal") then displayInternal = flagStr(props.Internal)
  end if

  captured = ""
  dt = CreateObject("roDateTime")
  if dt <> invalid
    dt.Mark()
    captured = dt.ToISOString()
  end if

  ' Prefer UI pixel size when display size AA is empty.
  if w = "" and uiW <> "" then w = uiW
  if h = "" and uiH <> "" then h = uiH

  summary = w + "x" + h
  if uiName <> "" then summary = summary + " ui=" + uiName
  if videoMode <> "" then summary = summary + " mode=" + videoMode
  summary = summary + " HDR10=" + hdr10
  if dolbyVision = "true" then summary = summary + " DV=true"
  if hlg = "true" then summary = summary + " HLG=true"
  if model <> "" then summary = summary + " model=" + model

  m.registry.write("displayWidth", w)
  m.registry.write("displayHeight", h)
  m.registry.write("uiResolution", uiName)
  m.registry.write("uiWidth", uiW)
  m.registry.write("uiHeight", uiH)
  m.registry.write("videoMode", videoMode)
  m.registry.write("displayAspect", aspect)
  m.registry.write("hdr10", hdr10)
  m.registry.write("hdr10Plus", hdr10Plus)
  m.registry.write("hlg", hlg)
  m.registry.write("dolbyVision", dolbyVision)
  m.registry.write("hdrSeamless", hdrSeamless)
  m.registry.write("displayInternal", displayInternal)
  m.registry.write("deviceModel", model)
  m.registry.write("deviceModelName", modelName)
  m.registry.write("deviceId", deviceId)
  m.registry.write("capturedAt", captured)
  m.registry.write("displaySummary", summary)
  m.registry.flush()

  m.displaySummary = summary + " (uploading...)"
  refreshProbeRowLabel()
  updateFooter()

  profile = {
    client: "JellyFlam3"
    deviceId: deviceId
    deviceModel: model
    deviceModelName: modelName
    displayWidth: w
    displayHeight: h
    uiResolution: uiName
    uiWidth: uiW
    uiHeight: uiH
    videoMode: videoMode
    displayAspect: aspect
    hdr10: hdr10
    hdr10Plus: hdr10Plus
    hlg: hlg
    dolbyVision: dolbyVision
    hdrSeamless: hdrSeamless
    displayInternal: displayInternal
    capturedAt: captured
    displaySummary: summary
    channelVersion: channelVersionString()
    schemaVersion: 1
  }
  postDisplayProfileToPi(profile)
end sub

sub postDisplayProfileToPi(profile as object)
  sink = resolveDisplaySinkUrl()
  if sink = ""
    m.displaySummary = readDisplaySummary() + " | Pi sink URL unknown (set baseUrl)"
    refreshProbeRowLabel()
    updateFooter()
    return
  end if
  token = m.registry.read("displaySinkToken")
  if token = invalid then token = ""
  m.sinkTask = createObject("roSGNode", "JellyfinTask")
  m.sinkTask.observeField("resultJson", "onDisplaySinkResult")
  m.sinkTask.command = "displayProfile"
  m.sinkTask.displaySinkUrl = sink
  m.sinkTask.sinkToken = token
  m.sinkTask.profileJson = FormatJson(profile)
  m.sinkTask.control = "RUN"
end sub

sub onDisplaySinkResult()
  if m.sinkTask = invalid then return
  raw = m.sinkTask.resultJson
  m.sinkTask = invalid
  baseSummary = m.registry.read("displaySummary")
  if baseSummary = invalid then baseSummary = ""
  res = invalid
  if raw <> invalid and raw <> "" then res = ParseJson(raw)
  if res = invalid
    m.displaySummary = baseSummary + " | Pi upload: bad response"
  else if res.ok = true
    fname = ""
    if res.file <> invalid then fname = res.file
    if fname <> ""
      m.displaySummary = baseSummary + " | Pi OK " + fname
    else
      m.displaySummary = baseSummary + " | Pi OK"
    end if
    m.registry.write("displaySummary", m.displaySummary)
    m.registry.flush()
  else
    err = "upload failed"
    if res.error <> invalid then err = res.error
    m.displaySummary = baseSummary + " | Pi " + err
  end if
  refreshProbeRowLabel()
  updateFooter()
end sub

sub editField(name as string)
  if isOkToggleField(name)
    toggleChoice(name)
    return
  end if
  kb = createObject("roSGNode", "StandardKeyboardDialog")
  kb.title = "Edit " + name
  cur = m.values[name]
  if cur = invalid then cur = ""
  kb.text = cur
  if name = "apiKey"
    teb = kb.textEditBox
    if teb <> invalid then teb.secureMode = true
  end if
  kb.buttons = ["OK", "Cancel"]
  kb.observeField("buttonSelected", "onKeyboardButton")
  kb.observeField("wasClosed", "onKeyboardClosed")
  m.keyboard = kb
  m.editingField = name
  scene = m.top.getScene()
  if scene <> invalid
    scene.dialog = kb
  else
    m.top.appendChild(kb)
    kb.setFocus(true)
  end if
end sub

sub keyboardEnteredText() as string
  if m.keyboard = invalid then return ""
  text = m.keyboard.text
  if (text = invalid or text = "") and m.keyboard.textEditBox <> invalid
    text = m.keyboard.textEditBox.text
  end if
  if text = invalid then return ""
  return text.Trim()
end sub

sub onKeyboardButton()
  if m.keyboard = invalid then return
  applyOk = false
  if m.keyboard.buttonSelected = 0 then applyOk = true
  dismissKeyboard(applyOk)
end sub

sub onKeyboardClosed()
  if m.keyboard = invalid then return
  dismissKeyboard(false)
end sub

sub dismissKeyboard(applyOk as boolean)
  if m.keyboard = invalid then return
  name = m.editingField
  if applyOk = true
    text = keyboardEnteredText()
    accepted = applyEditedValue(name, text)
    if accepted = true
      ' Persist each accepted edit now. Back should never silently discard a
      ' value that the keyboard's OK button already accepted.
      val = m.values[name]
      if val = invalid then val = ""
      if name = "baseUrl"
        while Len(val) > 0 and Right(val, 1) = "/"
          val = Left(val, Len(val) - 1)
        end while
        m.values[name] = val
      end if
      m.registry.write(name, val)
      m.registry.flush()
      m.top.saved = true
    end if
    refreshRowLabel(name)
  end if
  scene = m.top.getScene()
  if scene <> invalid then scene.dialog = invalid
  if m.keyboard <> invalid and m.keyboard.getParent() <> invalid
    m.top.removeChild(m.keyboard)
  end if
  m.keyboard = invalid
  m.editingField = ""
  focusIndex(m.idx)
end sub

sub saveAndClose()
  for each name in m.fields
    val = m.values[name]
    if val = invalid then val = ""
    if name = "baseUrl"
      val = val.Trim()
      while Len(val) > 0 and Right(val, 1) = "/"
        val = Left(val, Len(val) - 1)
      end while
      if isValidBaseUrl(val) <> true
        m.inputNotice = "baseUrl invalid - use http:// or https:// host"
        updateFooter()
        return
      end if
    else if name = "apiKey"
      if isValidApiKey(val) <> true
        m.inputNotice = "apiKey invalid - paste the Jellyfin key (no spaces)"
        updateFooter()
        return
      end if
    else if name = "userId" or name = "libraryId"
      if isHexDashId(val) <> true
        m.inputNotice = name + " invalid - use a Jellyfin GUID"
        updateFooter()
        return
      end if
    else if name = "streamMode"
      if isValidStreamMode(val) <> true
        m.inputNotice = "streamMode invalid - use mp4 or hls"
        updateFooter()
        return
      end if
      val = LCase(val.Trim())
    else if name = "commercialMode"
      if isValidBoolToken(val) <> true
        m.inputNotice = "commercialMode invalid - use true or false"
        updateFooter()
        return
      end if
      val = normalizeBool(val, false)
    else if name = "shuffleFlock"
      if isValidBoolToken(val) <> true
        m.inputNotice = "shuffleFlock invalid - use true or false"
        updateFooter()
        return
      end if
      val = normalizeBool(val, true)
    else if name = "titleMode"
      if isValidTitleMode(val) <> true
        m.inputNotice = "titleMode invalid - use filename or alias"
        updateFooter()
        return
      end if
      val = normalizeTitleMode(val)
    end if
    m.registry.write(name, val)
  end for
  m.registry.flush()
  m.top.saved = true
  m.top.close = true
end sub

function onKeyEvent(key as string, press as boolean) as boolean
  if not press then return false
  if m.keyboard <> invalid then return false
  if key = "back"
    m.top.close = true
    return true
  end if
  return false
end function
