function onKeyEvent(key as string, press as boolean) as boolean
  if not press then return false
  ' RowList often swallows options before Scene.onKeyEvent sees it
  if key = "options" or key = "info" or key = "lit_asterisk"
    m.top.requestSettings = true
    return true
  end if
  ' RowList has no wrap field. Slide normally in the middle; jump only at an end.
  if wrapGridKey(key) then return true
  return false
end function

' Horizontal wrap stays on the current row. Vertical wrap keeps the column and
' clamps it when the destination row is shorter (the last row of a partial flock).
' One tile or one row does not wrap, so a small flock stays put at that edge.
function wrapGridKey(key as string) as boolean
  if m.top.content = invalid then return false
  focused = m.top.rowItemFocused
  if focused = invalid or focused.count() < 2 then return false
  row = focused[0]
  col = focused[1]
  rowCount = m.top.content.getChildCount()
  if rowCount <= 0 or row < 0 or row >= rowCount then return false
  rowNode = m.top.content.getChild(row)
  if rowNode = invalid then return false
  colCount = rowNode.getChildCount()
  if colCount <= 0 then return false

  if key = "right" or key = "left"
    if colCount <= 1 then return false
    if key = "right" and col < colCount - 1 then return false
    if key = "left" and col > 0 then return false
    dest = 0
    if key = "left" then dest = colCount - 1
    m.top.jumpToItem(row, dest)
    return true
  end if

  if key = "down" or key = "up"
    if rowCount <= 1 then return false
    if key = "down" and row < rowCount - 1 then return false
    if key = "up" and row > 0 then return false
    destRow = 0
    if key = "up" then destRow = rowCount - 1
    m.top.jumpToItem(destRow, clampedColumn(destRow, col))
    return true
  end if
  return false
end function

function clampedColumn(rowIndex as integer, column as integer) as integer
  if m.top.content = invalid then return 0
  rowNode = m.top.content.getChild(rowIndex)
  if rowNode = invalid then return 0
  count = rowNode.getChildCount()
  if count <= 0 then return 0
  if column < 0 then return 0
  if column >= count then return count - 1
  return column
end function
