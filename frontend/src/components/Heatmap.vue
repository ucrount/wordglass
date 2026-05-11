<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    /** Map of "YYYY-MM-DD" → activity count */
    data: Record<string, number>;
    /** Number of weeks to show (default 12 ≈ 3 months) */
    weeks?: number;
  }>(),
  { weeks: 12 }
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

// Build a column-major grid: weeks (oldest → newest), each column is 7 days
// (Mon..Sun). Rightmost column contains today.
const grid = computed<Cell[][]>(() => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const dayOfWeek = (today.getDay() + 6) % 7; // 0=Mon..6=Sun
  const sundayDelta = 6 - dayOfWeek;
  const lastSunday = new Date(today);
  lastSunday.setDate(lastSunday.getDate() + sundayDelta);

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

// Month labels: place above the column where a new month starts
const monthLabels = computed<{ col: number; label: string }[]>(() => {
  const labels: { col: number; label: string }[] = [];
  let lastMonth = -1;
  grid.value.forEach((col, i) => {
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
    <div class="months">
      <div class="day-spacer" />
      <div class="month-cells">
        <span
          v-for="m in monthLabels"
          :key="m.col + m.label"
          class="month-label"
          :style="`grid-column: ${m.col + 1}`"
        >
          {{ m.label }}
        </span>
      </div>
    </div>

    <!-- Grid area: day labels + cells -->
    <div class="grid-area">
      <div class="day-labels">
        <span v-for="(d, i) in dayLabels" :key="i" class="day-label">{{ d }}</span>
      </div>
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

    <!-- Legend -->
    <div class="legend">
      <span class="legend-label">少</span>
      <span class="cell-mini level-0" />
      <span class="cell-mini level-1" />
      <span class="cell-mini level-2" />
      <span class="cell-mini level-3" />
      <span class="cell-mini level-4" />
      <span class="legend-label">多</span>
    </div>
  </div>
</template>

<style scoped>
.heatmap {
  --gap: 5px;
  --label-w: 26px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

/* Month labels row */
.months {
  display: grid;
  grid-template-columns: var(--label-w) 1fr;
  gap: var(--gap);
  font-size: 11px;
  color: var(--text-tertiary);
  height: 14px;
}

.month-cells {
  display: grid;
  grid-template-columns: repeat(v-bind("grid.length"), 1fr);
  gap: var(--gap);
  position: relative;
}

.month-label {
  white-space: nowrap;
  align-self: end;
  letter-spacing: -0.01em;
}

/* Grid area */
.grid-area {
  display: grid;
  grid-template-columns: var(--label-w) 1fr;
  gap: var(--gap);
}

.day-labels {
  display: grid;
  grid-template-rows: repeat(7, 1fr);
  gap: var(--gap);
}

.day-label {
  font-size: 10px;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

.cells {
  display: grid;
  grid-template-columns: repeat(v-bind("grid.length"), 1fr);
  gap: var(--gap);
  min-width: 0;
}

.col {
  display: grid;
  grid-template-rows: repeat(7, 1fr);
  gap: var(--gap);
}

.cell {
  aspect-ratio: 1;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.06);
  transition: transform 120ms ease, box-shadow 200ms ease;
}

[data-theme="dark"] .cell {
  background: rgba(255, 255, 255, 0.06);
}

.cell:hover {
  transform: scale(1.12);
  box-shadow: 0 0 0 2px var(--glass-border);
  z-index: 2;
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

/* Legend */
.legend {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 10px;
  color: var(--text-tertiary);
}

.legend-label { margin: 0 4px; }

.cell-mini {
  width: 11px;
  height: 11px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.06);
}

[data-theme="dark"] .cell-mini {
  background: rgba(255, 255, 255, 0.06);
}

.cell-mini.level-1 { background: rgba(139, 92, 246, 0.30); }
.cell-mini.level-2 { background: rgba(139, 92, 246, 0.55); }
.cell-mini.level-3 { background: rgba(139, 92, 246, 0.80); }
.cell-mini.level-4 { background: rgba(139, 92, 246, 1); }
</style>
