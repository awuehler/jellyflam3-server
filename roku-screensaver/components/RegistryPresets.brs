' Apply furnace-built pkg:/registry/jellyflam3-presets.json when registry keys are empty.
' Screensaver always rotates stills; do not write shuffleFlock (VoD owns that key).

function applyJellyFlam3PackPresets(reg as object) as boolean
  raw = ReadAsciiFile("pkg:/registry/jellyflam3-presets.json")
  if raw = invalid or raw = "" then return false
  data = ParseJson(raw)
  if data = invalid then return false

  keys = ["baseUrl", "apiKey", "userId", "libraryId", "commercialMode", "streamMode"]
  wrote = false
  for each k in keys
    v = data.lookup(k)
    if v = invalid then v = ""
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
