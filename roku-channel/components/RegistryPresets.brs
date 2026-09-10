' Apply furnace-built pkg:/registry/jellyflam3-presets.json when registry keys are empty.
' Do not write shuffleFlock. HomeScene always persists "true"; copying the package
' value used to flip devices to false on every sideload (JSON boolean or "false").

function jsonPresetStr(v as dynamic) as string
  if v = invalid then return ""
  tv = type(v)
  if tv = "Boolean" or tv = "roBoolean"
    if v = true then return "true"
    return "false"
  end if
  if tv = "Integer" or tv = "roInt" or tv = "roInteger" or tv = "Float" or tv = "roFloat" or tv = "Double" or tv = "roDouble"
    return v.toStr()
  end if
  s = ""
  s = v
  if GetInterface(s, "ifString") <> invalid then return s.Trim()
  return v.toStr()
end function

function applyJellyFlam3PackPresets(reg as object) as boolean
  raw = ReadAsciiFile("pkg:/registry/jellyflam3-presets.json")
  if raw = invalid or raw = "" then return false
  data = ParseJson(raw)
  if data = invalid then return false

  keys = ["baseUrl", "apiKey", "userId", "libraryId", "commercialMode", "streamMode"]
  wrote = false
  for each k in keys
    v = jsonPresetStr(data.lookup(k))
    cur = reg.read(k)
    if cur = invalid or cur = ""
      if v <> ""
        reg.write(k, v)
        wrote = true
      end if
    end if
  end for
  if wrote then reg.flush()
  return wrote
end function
