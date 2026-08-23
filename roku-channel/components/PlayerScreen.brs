sub init()
  m.video = m.top.findNode("Video")
  m.status = m.top.findNode("status")
  m.progressTimer = m.top.findNode("progressTimer")
  m.video.observeField("state", "onState")
  m.video.observeField("errorCode", "onError")
  m.video.observeField("errorMsg", "onError")
  m.video.observeField("position", "onPosition")
  m.progressTimer.observeField("fire", "onProgressFire")
  m.registry = CreateObject("roRegistrySection", "JellyFlam3")
  m.itemId = ""
  m.reportedPlaying = false
  m.streamFormat = "mp4"
  m.hlsUrl = ""
  m.mp4Url = ""
  m.title = ""
  m.lengthSec = 0
  m.triedAltFallback = false
  m.reloopPending = false
  m.advancePending = false
  ' Finer position ticks help catch end-of-clip before "finished".
  m.video.notificationInterval = 0.25
end sub

' Ambient dream loop defaults to Static MP4.
' Registry streamMode=hls keeps remux path for lab compare.
function resolveStreamMode() as string
  mode = m.registry.read("streamMode")
  if mode = invalid then mode = ""
  mode = LCase(mode.Trim())
  if mode = "hls" then return "hls"
  return "mp4"
end function

function shouldShuffleAdvance() as boolean
  if m.top.allowShuffleAdvance = true then return true
  return false
end function

sub playSheep(item as object)
  ' Always stop before (re)starting — Roku allows only one Video play instance
  stopPlaybackReport()
  m.video.control = "stop"
  m.itemId = ""
  if item <> invalid and item.id <> invalid then m.itemId = item.id
  m.reportedPlaying = false
  m.triedAltFallback = false
  m.reloopPending = false
  m.advancePending = false
  m.top.clipFinished = false
  m.hlsUrl = ""
  m.mp4Url = ""
  m.title = ""
  m.lengthSec = 0
  if item <> invalid
    if item.hlsUrl <> invalid and item.hlsUrl <> ""
      m.hlsUrl = item.hlsUrl
    else if item.url <> invalid and Instr(1, LCase(item.url), "m3u8") > 0
      m.hlsUrl = item.url
    end if
    if item.mp4Url <> invalid then m.mp4Url = item.mp4Url
    if item.title <> invalid then m.title = item.title
    if item.length <> invalid then m.lengthSec = item.length
  end if

  mode = resolveStreamMode()
  if mode = "hls" and m.hlsUrl <> ""
    m.streamFormat = "hls"
    startVideo(m.hlsUrl, "hls")
  else if m.mp4Url <> ""
    m.streamFormat = "mp4"
    startVideo(m.mp4Url, "mp4")
  else if m.hlsUrl <> ""
    m.streamFormat = "hls"
    startVideo(m.hlsUrl, "hls")
  else if item <> invalid and item.url <> invalid
    fmt = "mp4"
    if item.streamFormat <> invalid and item.streamFormat <> "" then fmt = LCase(item.streamFormat)
    m.streamFormat = fmt
    startVideo(item.url, fmt)
  end if
end sub

sub startVideo(url as string, fmt as string)
  content = createObject("roSGNode", "ContentNode")
  content.url = url
  content.streamFormat = fmt
  if m.title <> invalid then content.title = m.title
  if m.lengthSec <> invalid and m.lengthSec > 0 then content.length = m.lengthSec
  if m.status <> invalid
    label = m.title
    if label = invalid or label = "" then label = "sheep"
    m.status.text = "Loading " + label + " (" + fmt + ")..."
    m.status.visible = true
  end if
  m.video.content = content
  m.video.visible = true
  ' Manual seek-reloop (onPosition/finished) — Video.loop alone still gaps on Roku VOD.
  m.video.loop = false
  m.video.enableUI = false
  m.video.control = "play"
  m.video.setFocus(true)
end sub

sub stopSheep()
  stopPlaybackReport()
  if m.video <> invalid
    m.video.control = "stop"
    m.video.content = invalid
    m.video.visible = false
  end if
end sub

sub stopPlaybackReport()
  if m.progressTimer <> invalid then m.progressTimer.control = "stop"
  if m.reportedPlaying = true and m.itemId <> ""
    postPlayback("stopped")
  end if
  m.reportedPlaying = false
end sub

function playMethodForSessions() as string
  if m.streamFormat = "mp4" then return "DirectPlay"
  return "DirectStream"
end function

sub postPlayback(command as string)
  if m.itemId = "" then return
  base = m.registry.read("baseUrl")
  key = m.registry.read("apiKey")
  if base = invalid or base = "" then return
  if key = invalid or key = "" then return

  ' Do not use variable name "pos" — conflicts with builtin Pos()
  seconds = 0
  if m.video <> invalid and m.video.position <> invalid then seconds = m.video.position
  tickCount = Int(seconds * 10000000)

  jfTask = createObject("roSGNode", "JellyfinTask")
  jfTask.baseUrl = base
  jfTask.apiKey = key
  jfTask.userId = m.registry.read("userId")
  jfTask.libraryId = m.registry.read("libraryId")
  jfTask.command = command
  jfTask.itemId = m.itemId
  jfTask.positionTicks = tickCount
  jfTask.playMethod = playMethodForSessions()
  jfTask.control = "RUN"
end sub

sub onProgressFire()
  if m.reportedPlaying = true then postPlayback("progress")
end sub

function clipDurationSec() as float
  dur = 0.0
  if m.video <> invalid and m.video.duration <> invalid and m.video.duration > 0
    dur = m.video.duration
  else if m.lengthSec <> invalid and m.lengthSec > 0
    dur = m.lengthSec
  end if
  return dur
end function

' Seek to 0 without tearing down ContentNode — tighter than stop/rebuild (still may micro-gap).
sub seekReloop()
  if m.video = invalid then return
  if m.reloopPending = true then return
  m.reloopPending = true
  m.video.seek = 0
  if m.video.state <> "playing" and m.video.state <> "buffering"
    m.video.control = "play"
  end if
end sub

' allowShuffleAdvance: ask HomeScene for the next archive-gen sheep instead of reloop.
sub requestClipAdvance()
  if m.advancePending = true then return
  m.advancePending = true
  stopPlaybackReport()
  if m.video <> invalid then m.video.control = "stop"
  m.top.clipFinished = true
end sub

sub endOfClipAction()
  if shouldShuffleAdvance()
    requestClipAdvance()
  else
    seekReloop()
  end if
end sub

sub onPosition()
  if m.video = invalid then return
  if m.video.state <> "playing" then return
  if m.advancePending = true then return
  dur = clipDurationSec()
  if dur <= 1.0 then return
  cur = m.video.position
  if cur = invalid then return
  ' Jump before EOF so we avoid the heavier "finished" path when possible.
  if cur >= (dur - 0.4) and cur > 0.5
    endOfClipAction()
  end if
end sub

sub tryAltFallback() as boolean
  if m.triedAltFallback = true then return false
  altUrl = ""
  altFmt = ""
  if m.streamFormat = "hls" and m.mp4Url <> ""
    altUrl = m.mp4Url
    altFmt = "mp4"
  else if m.streamFormat = "mp4" and m.hlsUrl <> ""
    altUrl = m.hlsUrl
    altFmt = "hls"
  end if
  if altUrl = "" then return false

  m.triedAltFallback = true
  m.reloopPending = false
  m.streamFormat = altFmt
  m.reportedPlaying = false
  if m.progressTimer <> invalid then m.progressTimer.control = "stop"
  if m.status <> invalid
    m.status.visible = true
    m.status.text = "Retrying as " + altFmt + "..."
  end if
  m.video.control = "stop"
  startVideo(altUrl, altFmt)
  return true
end sub

sub onState()
  st = m.video.state
  if st = "playing"
    m.reloopPending = false
    if m.reportedPlaying = false and m.itemId <> ""
      postPlayback("playing")
      m.reportedPlaying = true
      if m.progressTimer <> invalid then m.progressTimer.control = "start"
    end if
  else if st = "finished"
    if shouldShuffleAdvance()
      requestClipAdvance()
    else
      ' Backup if position seek missed EOF — keep same ContentNode.
      seekReloop()
      m.video.control = "play"
    end if
    return
  end if
  if m.status = invalid then return
  if st = "buffering" or st = "connecting"
    ' Suppress status flash during ambient seek-reloop (gap still happens; less UI noise).
    if m.reloopPending = true
      m.status.visible = false
    else
      m.status.visible = true
      m.status.text = "Buffering (" + m.streamFormat + ")..."
    end if
  else if st = "playing"
    m.status.visible = false
  else if st = "error"
    if tryAltFallback() then return
    m.status.visible = true
    msg = m.video.errorMsg
    if msg = invalid or msg = "" then msg = "playback error"
    m.status.text = msg
  end if
end sub

sub onError()
  if tryAltFallback() then return
  if m.status = invalid then return
  msg = m.video.errorMsg
  code = m.video.errorCode
  m.status.visible = true
  if msg = invalid or msg = "" then msg = "playback error"
  if code <> invalid then msg = msg + " (" + code.toStr() + ")"
  m.status.text = msg
end sub

function onKeyEvent(key as string, press as boolean) as boolean
  if press and (key = "back" or key = "up")
    stopSheep()
    m.top.close = true
    return true
  end if
  return false
end function
