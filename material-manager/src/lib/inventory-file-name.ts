function buildDateLabel() {
  const current = new Date();
  const month = current.getMonth() + 1;
  const day = current.getDate();

  return `${month}.${day}`;
}

export function buildInventoryFileName(extension: "png" | "xlsx") {
  return `${buildDateLabel()}松戸ヤード資材数量表.${extension}`;
}