// One square per round, by how close the two words were. The last round is the
// win. Same idea as Wordle's grid: it shows how the game went without giving
// the words away, so the starting pair works as a hook for whoever reads it.
function square(round) {
  if (round.is_won) return "🟩";
  const pct = Math.round((round.player_computer_similarity ?? 0) * 100);
  if (pct >= 55) return "🟨";
  if (pct >= 30) return "🟧";
  return "🟥";
}

export function shareText(history, language, url) {
  const isHe = language === "he";
  const first = history[0];
  const rounds = history.length;
  const grid = history.map(square).join("");
  const lines = isHe
    ? [`אמצע 🎯 נפגשתי עם המחשב באמצע בסיבוב ${rounds}`, `התחלנו מ: ${first.word1} + ${first.word2}`, grid, url]
    : [`Amtza 🎯 Met the computer in the middle in ${rounds} round${rounds === 1 ? "" : "s"}`,
       `Started from: ${first.word1} + ${first.word2}`, grid, url];
  return lines.join("\n");
}
