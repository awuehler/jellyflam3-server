' Screensaver options: crossfade + dwell (+ fade duration). VoD owns Jellyfin credentials.

sub init()
  m.reg = CreateObject("roRegistrySection", "JellyFlam3")
  m.credStatus = m.top.findNode("credStatus")
  m.rows = [
    m.top.findNode("row0"),
    m.top.findNode("row1"),
    m.top.findNode("row2")
  ]
  m.rowBgs = [
    m.top.findNode("row0bg"),
    m.top.findNode("row1bg"),
    m.top.findNode("row2bg")
  ]
  m.cursor = 0
  m.dwellChoices = [8, 12, 20, 30]
  m.fadeSecChoices = [0.5, 1.0, 1.5, 2.5]

  m.fadeOn = registryBool(m.reg, "ssFade", true)
  m.dwellSec = registryInt(m.reg, "ssDwellSec", 12)
  m.fadeSec = registryFloat(m.reg, "ssFadeSec", 1.5)
  ' Snap dwell/fade to nearest choice
  m.dwellIdx = nearestIndex(m.dwellChoices, m.dwellSec)
  m.fadeSecIdx = nearestIndexFloat(m.fadeSecChoices, m.fadeSec)
  m.dwellSec = m.dwellChoices[m.dwellIdx]
  m.fadeSec = m.fadeSecChoices[m.fadeSecIdx]

  refreshCredStatus()
  refreshRows()
  m.top.backExitsScene = true
  m.top.setFocus(true)
end sub

function registryBool(reg as object, key as string, defaultVal as boolean) as boolean
  raw = reg.read(key)
  if raw = invalid or raw = "" then return defaultVal
  low = LCase(raw)
  if low = "true" or low = "1" or low = "yes" or low = "on" then return true
  if low = "false" or low = "0" or low = "no" or low = "off" then return false
  return defaultVal
end function

function registryInt(reg as object, key as string, defaultVal as integer) as integer
  raw = reg.read(key)
  if raw = invalid or raw = "" then return defaultVal
  return raw.toInt()
end function

function registryFloat(reg as object, key as string, defaultVal as float) as float
  raw = reg.read(key)
  if raw = invalid or raw = "" then return defaultVal
  return Val(raw)
end function

function nearestIndex(choices as object, value as integer) as integer
  best = 0
  bestDiff = 999999
  i = 0
  while i < choices.count()
    d = Abs(choices[i] - value)
    if d < bestDiff
      bestDiff = d
      best = i
    end if
    i = i + 1
  end while
  return best
end function

function nearestIndexFloat(choices as object, value as float) as integer
  best = 0
  bestDiff = 999999.0
  i = 0
  while i < choices.count()
    d = Abs(choices[i] - value)
    if d < bestDiff
      bestDiff = d
      best = i
    end if
    i = i + 1
  end while
  return best
end function

sub refreshCredStatus()
  missing = []
  if blank(m.reg.read("baseUrl")) then missing.push("baseUrl")
  if blank(m.reg.read("apiKey")) then missing.push("apiKey")
  if blank(m.reg.read("userId")) then missing.push("userId")
  if blank(m.reg.read("libraryId")) then missing.push("libraryId")
  if missing.count() = 0
    m.credStatus.text = "Jellyfin registry: OK (saved by VoD channel Settings on this device)"
    m.credStatus.color = "0x88FF88FF"
  else
    line = missing[0]
    i = 1
    while i < missing.count()
      line = line + ", " + missing[i]
      i = i + 1
    end while
    m.credStatus.text = "Missing (need VoD channel Settings first): " + line
    m.credStatus.color = "0xFFAA66FF"
  end if
end sub

function blank(v as dynamic) as boolean
  return v = invalid or v = ""
end function

sub refreshRows()
  fadeLabel = "Off"
  if m.fadeOn then fadeLabel = "On"
  m.rows[0].text = "Crossfade                    " + fadeLabel
  m.rows[1].text = "Dwell between images         " + m.dwellSec.toStr() + " s"
  m.rows[2].text = "Fade duration                " + fadeSecLabel(m.fadeSec)

  i = 0
  while i < m.rowBgs.count()
    if i = m.cursor
      m.rowBgs[i].color = "0x2A3A5AFF"
      m.rows[i].color = "0xFFFFFFFF"
    else
      m.rowBgs[i].color = "0x1A1A28FF"
      m.rows[i].color = "0xE8E8F0FF"
    end if
    i = i + 1
  end while
end sub

function fadeSecLabel(sec as float) as string
  ' BrightScript has no printf; trim trailing zeros lightly
  if sec = 0.5 then return "0.5 s"
  if sec = 1.0 then return "1 s"
  if sec = 1.5 then return "1.5 s"
  if sec = 2.5 then return "2.5 s"
  return sec.toStr() + " s"
end function

sub saveAll()
  fadeVal = "false"
  if m.fadeOn then fadeVal = "true"
  m.reg.write("ssFade", fadeVal)
  m.reg.write("ssDwellSec", m.dwellSec.toStr())
  m.reg.write("ssFadeSec", fadeSecStorage(m.fadeSec))
  m.reg.flush()
end sub

function fadeSecStorage(sec as float) as string
  if sec = 0.5 then return "0.5"
  if sec = 1.0 then return "1.0"
  if sec = 1.5 then return "1.5"
  if sec = 2.5 then return "2.5"
  return sec.toStr()
end function

sub nudge(delta as integer)
  if m.cursor = 0
    m.fadeOn = not m.fadeOn
  else if m.cursor = 1
    m.dwellIdx = m.dwellIdx + delta
    if m.dwellIdx < 0 then m.dwellIdx = m.dwellChoices.count() - 1
    if m.dwellIdx >= m.dwellChoices.count() then m.dwellIdx = 0
    m.dwellSec = m.dwellChoices[m.dwellIdx]
  else if m.cursor = 2
    m.fadeSecIdx = m.fadeSecIdx + delta
    if m.fadeSecIdx < 0 then m.fadeSecIdx = m.fadeSecChoices.count() - 1
    if m.fadeSecIdx >= m.fadeSecChoices.count() then m.fadeSecIdx = 0
    m.fadeSec = m.fadeSecChoices[m.fadeSecIdx]
  end if
  saveAll()
  refreshRows()
end sub

function onKeyEvent(key as string, press as boolean) as boolean
  if not press then return false
  if key = "up"
    m.cursor = m.cursor - 1
    if m.cursor < 0 then m.cursor = m.rows.count() - 1
    refreshRows()
    return true
  else if key = "down"
    m.cursor = m.cursor + 1
    if m.cursor >= m.rows.count() then m.cursor = 0
    refreshRows()
    return true
  else if key = "left"
    nudge(-1)
    return true
  else if key = "right" or key = "OK"
    nudge(1)
    return true
  else if key = "back"
    ' Let Scene.backExitsScene close (focus already on scene).
    return false
  end if
  return false
end function
