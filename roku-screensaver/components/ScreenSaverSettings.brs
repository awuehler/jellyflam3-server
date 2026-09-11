' Screensaver options: Jellyfin credentials + crossfade / dwell.
' Private-channel VoD does not share this package's registry — Settings must write creds.

sub init()
  m.reg = CreateObject("roRegistrySection", "JellyFlam3")
  m.credStatus = m.top.findNode("credStatus")
  m.rows = [
    m.top.findNode("row0"),
    m.top.findNode("row1"),
    m.top.findNode("row2"),
    m.top.findNode("row3"),
    m.top.findNode("row4"),
    m.top.findNode("row5"),
    m.top.findNode("row6")
  ]
  m.rowBgs = [
    m.top.findNode("row0bg"),
    m.top.findNode("row1bg"),
    m.top.findNode("row2bg"),
    m.top.findNode("row3bg"),
    m.top.findNode("row4bg"),
    m.top.findNode("row5bg"),
    m.top.findNode("row6bg")
  ]
  m.credFields = ["baseUrl", "apiKey", "userId", "libraryId"]
  m.cursor = 0
  m.dwellChoices = [8, 12, 20, 30]
  m.fadeSecChoices = [0.5, 1.0, 1.5, 2.5]
  m.keyboard = invalid
  m.editingField = ""

  m.fadeOn = registryBool(m.reg, "ssFade", true)
  m.dwellSec = registryInt(m.reg, "ssDwellSec", 12)
  m.fadeSec = registryFloat(m.reg, "ssFadeSec", 1.5)
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

function blank(v as dynamic) as boolean
  return v = invalid or v = ""
end function

function maskSecret(raw as string) as string
  if raw = invalid or raw = "" then return "(empty)"
  n = Len(raw)
  if n <= 4 then return "****"
  return Left(raw, 2) + "..." + Right(raw, 2) + " (" + n.toStr() + " chars)"
end function

function credValue(name as string) as string
  v = m.reg.read(name)
  if v = invalid then return ""
  return v
end function

sub refreshCredStatus()
  missing = []
  for each name in m.credFields
    if blank(m.reg.read(name)) then missing.push(name)
  end for
  if missing.count() = 0
    m.credStatus.text = "Jellyfin registry: OK"
    m.credStatus.color = "0x88FF88FF"
  else
    line = missing[0]
    i = 1
    while i < missing.count()
      line = line + ", " + missing[i]
      i = i + 1
    end while
    m.credStatus.text = "Missing: " + line + " — OK on a row to paste"
    m.credStatus.color = "0xFFAA66FF"
  end if
end sub

sub refreshRows()
  base = credValue("baseUrl")
  if base = "" then base = "(empty)"
  api = maskSecret(credValue("apiKey"))
  uid = credValue("userId")
  if uid = "" then uid = "(empty)"
  lib = credValue("libraryId")
  if lib = "" then lib = "(empty)"
  fadeLabel = "Off"
  if m.fadeOn then fadeLabel = "On"
  m.rows[0].text = "Jellyfin URL                 " + base
  m.rows[1].text = "API key                      " + api
  m.rows[2].text = "User id                      " + uid
  m.rows[3].text = "Library id                   " + lib
  m.rows[4].text = "Crossfade                    " + fadeLabel
  m.rows[5].text = "Dwell between images         " + m.dwellSec.toStr() + " s"
  m.rows[6].text = "Fade duration                " + fadeSecLabel(m.fadeSec)

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
  if sec = 0.5 then return "0.5 s"
  if sec = 1.0 then return "1 s"
  if sec = 1.5 then return "1.5 s"
  if sec = 2.5 then return "2.5 s"
  return sec.toStr() + " s"
end function

sub saveFade()
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

sub nudgeFade(delta as integer)
  fadeCursor = m.cursor - m.credFields.count()
  if fadeCursor = 0
    m.fadeOn = not m.fadeOn
  else if fadeCursor = 1
    m.dwellIdx = m.dwellIdx + delta
    if m.dwellIdx < 0 then m.dwellIdx = m.dwellChoices.count() - 1
    if m.dwellIdx >= m.dwellChoices.count() then m.dwellIdx = 0
    m.dwellSec = m.dwellChoices[m.dwellIdx]
  else if fadeCursor = 2
    m.fadeSecIdx = m.fadeSecIdx + delta
    if m.fadeSecIdx < 0 then m.fadeSecIdx = m.fadeSecChoices.count() - 1
    if m.fadeSecIdx >= m.fadeSecChoices.count() then m.fadeSecIdx = 0
    m.fadeSec = m.fadeSecChoices[m.fadeSecIdx]
  end if
  saveFade()
  refreshRows()
end sub

sub editCred(name as string)
  kb = createObject("roSGNode", "KeyboardDialog")
  kb.title = "Edit " + name
  cur = credValue(name)
  kb.text = cur
  if name = "apiKey"
    teb = kb.textEditBox
    if teb <> invalid then teb.secureMode = true
  end if
  kb.buttons = ["OK", "Cancel"]
  m.top.backExitsScene = false
  m.top.appendChild(kb)
  kb.observeField("buttonSelected", "onKeyboardButton")
  kb.setFocus(true)
  m.keyboard = kb
  m.editingField = name
end sub

sub onKeyboardButton()
  if m.keyboard = invalid then return
  btn = m.keyboard.buttonSelected
  name = m.editingField
  if btn = 0
    text = m.keyboard.text
    if text = invalid then text = ""
    text = text.Trim()
    if name = "baseUrl"
      while Len(text) > 0 and Right(text, 1) = "/"
        text = Left(text, Len(text) - 1)
      end while
    end if
    m.reg.write(name, text)
    m.reg.flush()
  end if
  m.top.removeChild(m.keyboard)
  m.keyboard = invalid
  m.editingField = ""
  m.top.backExitsScene = true
  refreshCredStatus()
  refreshRows()
  m.top.setFocus(true)
end sub

function onKeyEvent(key as string, press as boolean) as boolean
  if not press then return false
  if m.keyboard <> invalid then return false
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
    if m.cursor < m.credFields.count()
      editCred(m.credFields[m.cursor])
    else
      nudgeFade(-1)
    end if
    return true
  else if key = "right" or key = "OK"
    if m.cursor < m.credFields.count()
      editCred(m.credFields[m.cursor])
    else
      nudgeFade(1)
    end if
    return true
  else if key = "back"
    return false
  end if
  return false
end function
