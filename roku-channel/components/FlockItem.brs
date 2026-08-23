sub init()
  m.poster = m.top.findNode("poster")
  m.placeholder = m.top.findNode("placeholder")
  m.focusRing = m.top.findNode("focusRing")
  m.title = m.top.findNode("title")
  m.meta = m.top.findNode("meta")
  m.poster.observeField("loadStatus", "onPosterLoad")
end sub

sub onContentChange()
  c = m.top.itemContent
  if c = invalid then return

  name = ""
  if c.title <> invalid then name = c.title
  m.title.text = name

  meta = ""
  if c.metaLine <> invalid then meta = c.metaLine
  if m.meta <> invalid then m.meta.text = meta

  url = ""
  if c.hdPosterUrl <> invalid then url = c.hdPosterUrl

  if url = invalid or url = ""
    showPlaceholder()
  else
    m.placeholder.visible = false
    m.poster.visible = true
    m.poster.uri = url
  end if
end sub

sub showPlaceholder()
  m.poster.uri = ""
  m.poster.visible = false
  m.placeholder.visible = true
  m.placeholder.text = "No poster"
end sub

sub onPosterLoad()
  st = m.poster.loadStatus
  if st = "failed" or st = "none"
    showPlaceholder()
  else if st = "ready" or st = "loading"
    if st = "ready"
      m.placeholder.visible = false
      m.poster.visible = true
    end if
  end if
end sub

sub onFocusPercent()
  fp = m.top.focusPercent
  if fp = invalid then fp = 0.0
  rfp = m.top.rowFocusPercent
  if rfp = invalid then rfp = 1.0
  focused = (fp > 0.5) and (rfp > 0.5)
  if m.focusRing <> invalid then m.focusRing.visible = focused
end sub
