export interface DiffToken {
  type: "same" | "added" | "removed";
  word: string;
}

// Compute simple word-level diff using Longest Common Subsequence
export function computeWordDiff(origStr: string, editStr: string): DiffToken[] {
  const orig = origStr.trim().split(/\s+/).filter(Boolean);
  const edit = editStr.trim().split(/\s+/).filter(Boolean);

  const n = orig.length;
  const m = edit.length;

  // LCS Matrix
  const dp: number[][] = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0));

  for (let i = 0; i < n; i++) {
    for (let j = 0; j < m; j++) {
      if (orig[i] === edit[j]) {
        dp[i + 1][j + 1] = dp[i][j] + 1;
      } else {
        dp[i + 1][j + 1] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  // Backtrack to find diff tokens
  const tokens: DiffToken[] = [];
  let i = n;
  let j = m;

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && orig[i - 1] === edit[j - 1]) {
      tokens.unshift({ type: "same", word: orig[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      tokens.unshift({ type: "added", word: edit[j - 1] });
      j--;
    } else if (i > 0 && (j === 0 || dp[i][j - 1] < dp[i - 1][j])) {
      tokens.unshift({ type: "removed", word: orig[i - 1] });
      i--;
    }
  }

  return tokens;
}
