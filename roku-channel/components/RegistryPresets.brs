' Apply furnace-built pkg:/registry/jellyflam3-presets.json when registry keys are empty.
' shuffleFlock is always synced from the package when present (furnace ambient policy).

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
  ' Force package shuffle policy onto device so re-sideload can flip ambient vs multi-sheep.
  sf = data.lookup("shuffleFlock")
  if sf <> invalid and sf <> ""
    if reg.read("shuffleFlock") <> sf
      reg.write("shuffleFlock", sf)
      wrote = true
    end if
  end if
  if wrote then reg.flush()
  return wrote
end function
