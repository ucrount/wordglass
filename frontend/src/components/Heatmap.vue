<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    /** Map of "YYYY-MM-DD" → activity count */
    data: Record<string, number>;
    /** Number of weeks to show (5 = ~35 days) */
    weeks?: number;
  }>(),
  { weeks: 5 }
);

interface Cell {
  date: string;
  count: number;
  level: 0 | 1 | 2 | 3 | 4;
  future: boolean;
  today: boolean;
}

function fmt(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function levelFor(count: number): 0 | 1 | 2 | 3 | 4 {
  if (count <= 0) return 0;
  if (count <= 3) return 1;
  if (count <= 8) return 2;
  if (count <= 20) return 3;
  return 4;
}

// Build a grid: 7 rows (Mon-Sun), N cols (weeks).
// Each col is a calendar week; the rightmost col contains today.
const grid = computed<Cell[][]>(() => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  // Walk back to the Monday of today's week to anchor the rightmost column
  const dayOfWeek = (today.getDay() + 6) % 7; // 0=Mon..6=Sun
  const sundayDelta = 6 - dayOfWeek;
  const lastSunday = new Date(today);
  lastSunday.setDate(lastSunday.getDate() + sundayDelta);

  // Build weeks from oldest to newest
  const cols: Cell[][] = [];
  for (let w = props.weeks - 1; w >= 0; w--) {
    const col: Cell[] = [];
    for (let d = 0; d < 7; d++) {
      const cellDate = new Date(lastSunday);
      cellDate.setDate(cellDate.getDate() - w * 7 - (6 - d));
      const iso = fmt(cellDate);
      const count = props.data[iso] ?? 0;
      col.push({
        date: iso,
        count,
        level: levelFor(count),
        future: cellDate > today,
        today: cellDate.getTime() === today.getTime(),
      });
    }
    cols.push(col);
  }
  return cols;
});

// Month labels (show the month name on the column where a month begins)
const monthLabels = computed<{ col: number; label: string }[]>(() => {
  const labels: { col: number; label: string }[] = [];
  let lastMonth = -1;
  grid.value.forEach((col, i) => {
    // Use the Sunday (last cell) date as the column's representative date
    const monday = col[0].date;
    const m = new Date(monday).getMonth();
    if (m !== lastMonth) {
      labels.push({ col: i, label: `${m + 1}月` });
      lastMonth = m;
    }
  });
  return labels;
});

const dayLabels = ["", "二", "", "四", "", "六", ""];
</script>

<template>
  <div class="heatmap">
    <!-- Month labels row -->
    <div class="months-row">
      <span class="day-spacer" />
      <span
        v-for="m in monthLabels"
        :key="m.col + m.label"
        class="month-label"
        :style="`grid-column: ${m.col + 2}`"
      >
        {{ m.label }}
      </span>
    </div>

    <div class="grid-row">
      <!-- Day labels column -->
      <div class="day-labels">
        <span v-for="d in dayLabels" :key="d" class="day-label">{{ d }}</span>
      </div>

      <!-- Cells -->
      <div class="cells">
        <div v-for="(col, ci) in grid" :key="ci" class="col">
          <span
            v-for="cell in col"
            :key="cell.date"
            class="cell"
            :class="[
              `level-${cell.level}`,
              { future: cell.future, today: cell.today },
            ]"
            :title="`${cell.date} · ${cell.count} 次活动`"
          />
        </div>
      </div>
    </div>

    <div class="legend">
      <span class="legend-label">少</span>
      <span class="cell level-0 small" />
      <span class="cell level-1 small" />
      <span class="cell level-2 small" />
      <span class="cell level-3 small" />
      <span class="cell level-4 small" />
      <span class="legend-label">多</span>
    </div>
  </div>
</template>

<style scoped>
.heatmap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.months-row {
  display: grid;
  grid-template-columns: 28px repeat(v-bind("grid.length"), 16px);
  gap: 4px;
  font-size: 11px;
  color: var(--text-tertiary);
  height: 14px;
}

.day-spacer { grid-column: 1; }

.month-label {
  grid-row: 1;
  white-space: nowrap;
}

.grid-row {
  display: flex;
  gap: 4px;
}

.day-labels {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 24px;
}

.day-label {
  height: 16px;
  font-size: 10px;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
}

.cells {
  display: flex;
  gap: 4px;
}

.col {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cell {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.06);
  transition: transform 120ms ease, box-shadow 200ms ease;
}

[data-theme="dark"] .cell {
  background: rgba(255, 255, 255, 0.06);
}

.cell:hover {
  transform: scale(1.18);
  box-shadow: 0 0 0 2px var(--glass-border);
}

.cell.future {
  background: transparent !important;
  border: 1px dashed var(--hairline);
}

.cell.today {
  box-shadow: 0 0 0 2px var(--brand);
}

.cell.level-1 { background: rgba(139, 92, 246, 0.30); }
.cell.level-2 { background: rgba(139, 92, 246, 0.55); }
.cell.level-3 { background: rgba(139, 92, 246, 0.80); }
.cell.level-4 { background: rgba(139, 92, 246, 1); box-shadow: 0 0 8px rgba(139, 92, 246, 0.5); }

.legend {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  font-size: 10px;
  color: var(--text-tertiary);
}

.legend-label { margin: 0 4px; }

.cell.small {
  width: 10px;
  height: 10px;
}
</style>
