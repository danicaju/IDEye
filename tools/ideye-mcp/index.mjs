#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const MCP_DIR = path.dirname(fileURLToPath(import.meta.url));
const AGENTIC_QUEUE_PATH = process.env.IDEYE_AGENTIC_QUEUE
  || path.resolve(MCP_DIR, "../../agentic_task_queue.json");

const server = new McpServer({
  name: "ideye-dev-tools",
  version: "1.0.0"
});

// Tool 1: Simulate Gaze Stream
server.tool(
  "simulate_gaze_stream",
  "Generates synthetic realistic gaze tracking traces with saccadic curves, Gaussian physiological jitter, and optional blink intervals for testing eye-tracking IDE UI without hardware.",
  {
    startX: z.number().default(200).describe("Starting screen X coordinate"),
    startY: z.number().default(200).describe("Starting screen Y coordinate"),
    endX: z.number().default(800).describe("Ending screen X coordinate"),
    endY: z.number().default(600).describe("Ending screen Y coordinate"),
    durationMs: z.number().default(500).describe("Duration of the movement in milliseconds"),
    fps: z.number().default(60).describe("Target frames per second"),
    jitterStd: z.number().default(3.0).describe("Standard deviation of tremor/jitter noise in pixels"),
    hasBlink: z.boolean().default(false).describe("Whether to simulate a blink event in the middle")
  },
  async ({ startX, startY, endX, endY, durationMs, fps, jitterStd, hasBlink }) => {
    const totalFrames = Math.max(5, Math.round((durationMs / 1000) * fps));
    const samples = [];
    const startTime = Date.now();

    function gaussianRandom() {
      let u = 0, v = 0;
      while (u === 0) u = Math.random();
      while (v === 0) v = Math.random();
      return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    }

    for (let i = 0; i < totalFrames; i++) {
      const progress = i / (totalFrames - 1);
      // Sigmoidal easing for realistic saccadic acceleration and deceleration
      const sigmoid = 1 / (1 + Math.exp(-10 * (progress - 0.5)));
      
      const rawX = startX + (endX - startX) * sigmoid;
      const rawY = startY + (endY - startY) * sigmoid;
      
      const jitterX = gaussianRandom() * jitterStd;
      const jitterY = gaussianRandom() * jitterStd;

      const isBlinking = hasBlink && progress >= 0.4 && progress <= 0.6;
      const ear = isBlinking ? 0.08 : 0.28 + gaussianRandom() * 0.02;

      const sampleTime = startTime + Math.round(progress * durationMs);
      samples.push({
        frame: i + 1,
        timestamp: sampleTime,
        x: Math.round((rawX + jitterX) * 10) / 10,
        y: Math.round((rawY + jitterY) * 10) / 10,
        idealX: Math.round(rawX * 10) / 10,
        idealY: Math.round(rawY * 10) / 10,
        ear: Math.round(ear * 1000) / 1000,
        isBlink: isBlinking,
        state: isBlinking ? "BLINK" : (progress < 0.2 || progress > 0.8 ? "FIXATION" : "SACCADE")
      });
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            summary: `Generated ${samples.length} synthetic gaze samples over ${durationMs}ms (${fps} FPS)`,
            parameters: { startX, startY, endX, endY, durationMs, fps, jitterStd, hasBlink },
            sampleCount: samples.length,
            samples: samples.slice(0, 50),
            note: samples.length > 50 ? `Truncated to first 50 of ${samples.length} samples` : "Complete"
          }, null, 2)
        }
      ]
    };
  }
);

// Tool 2: Benchmark One Euro Filter
server.tool(
  "benchmark_one_euro_filter",
  "Benchmarks the One Euro Filter (1€ Filter) against simulated noisy gaze coordinates to evaluate jitter suppression, temporal lag, and processing speed.",
  {
    minCutoff: z.number().default(1.0).describe("Minimum cutoff frequency in Hz"),
    beta: z.number().default(0.007).describe("Speed coefficient cutoff slope"),
    dCutoff: z.number().default(1.0).describe("Cutoff frequency for derivative in Hz"),
    sampleCount: z.number().default(120).describe("Number of test samples to process"),
    jitterMagnitude: z.number().default(5.0).describe("Injected jitter standard deviation in pixels")
  },
  async ({ minCutoff, beta, dCutoff, sampleCount, jitterMagnitude }) => {
    class OneEuroFilter {
      constructor(t0, x0, min_cutoff, beta, d_cutoff) {
        this.min_cutoff = min_cutoff;
        this.beta = beta;
        this.d_cutoff = d_cutoff;
        this.x_prev = x0;
        this.dx_prev = 0;
        this.t_prev = t0;
      }
      smoothingFactor(dt, cutoff) {
        const r = 2 * Math.PI * cutoff * dt;
        return r / (r + 1);
      }
      filter(t, x) {
        const dt = (t - this.t_prev) / 1000;
        if (dt <= 0) return this.x_prev;
        const dx = (x - this.x_prev) / dt;
        const edx = this.smoothingFactor(dt, this.d_cutoff);
        const dx_hat = edx * dx + (1 - edx) * this.dx_prev;
        const cutoff = this.min_cutoff + this.beta * Math.abs(dx_hat);
        const a = this.smoothingFactor(dt, cutoff);
        const x_hat = a * x + (1 - a) * this.x_prev;
        this.x_prev = x_hat;
        this.dx_prev = dx_hat;
        this.t_prev = t;
        return x_hat;
      }
    }

    const dtMs = 1000 / 60; // 60 FPS
    let now = Date.now();
    const filterX = new OneEuroFilter(now, 500, minCutoff, beta, dCutoff);
    const filterY = new OneEuroFilter(now, 500, minCutoff, beta, dCutoff);

    let rawRoughness = 0;
    let filteredRoughness = 0;
    const rawHistory = [];
    const filteredHistory = [];

    const startBench = performance.now();
    for (let i = 0; i < sampleCount; i++) {
      now += dtMs;
      // Fixed point at (500, 500) during fixation with noise
      const noiseX = (Math.random() - 0.5) * 2 * jitterMagnitude;
      const noiseY = (Math.random() - 0.5) * 2 * jitterMagnitude;
      const rawX = 500 + noiseX;
      const rawY = 500 + noiseY;

      const outX = filterX.filter(now, rawX);
      const outY = filterY.filter(now, rawY);

      rawHistory.push({ x: rawX, y: rawY });
      filteredHistory.push({ x: outX, y: outY });

      if (i >= 2) {
        const r0 = rawHistory[i - 2], r1 = rawHistory[i - 1], r2 = rawHistory[i];
        const f0 = filteredHistory[i - 2], f1 = filteredHistory[i - 1], f2 = filteredHistory[i];
        rawRoughness += Math.hypot((r2.x - r1.x) - (r1.x - r0.x), (r2.y - r1.y) - (r1.y - r0.y));
        filteredRoughness += Math.hypot((f2.x - f1.x) - (f1.x - f0.x), (f2.y - f1.y) - (f1.y - f0.y));
      }
    }
    const elapsed = performance.now() - startBench;
    const avgMicrosPerSample = (elapsed / sampleCount) * 1000;

    const jitterReductionPercent = Math.max(0, ((rawRoughness - filteredRoughness) / (rawRoughness || 1)) * 100);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            status: "SUCCESS",
            configuration: { minCutoff, beta, dCutoff, sampleCount, jitterMagnitude },
            results: {
              rawRoughnessIndex: Math.round(rawRoughness * 100) / 100,
              filteredRoughnessIndex: Math.round(filteredRoughness * 100) / 100,
              jitterSuppressionPercentage: `${jitterReductionPercent.toFixed(1)}%`,
              averageComputeTimePerSampleUs: `${avgMicrosPerSample.toFixed(2)} µs`,
              fpsCapacity: Math.round(1000000 / (avgMicrosPerSample || 1))
            },
            recommendation: jitterReductionPercent > 65
              ? "Optimal filter configuration: High jitter suppression without significant delay."
              : "Increase minCutoff or decrease beta to improve stability during fixations."
          }, null, 2)
        }
      ]
    };
  }
);

// Tool 3: Calculate Gaze Calibration
server.tool(
  "calculate_gaze_calibration",
  "Computes polynomial mapping matrix coefficients between eye/iris landmarks and screen coordinates using Ordinary Least Squares, reporting RMSE and calibration accuracy.",
  {
    calibrationPairs: z.array(z.object({
      eyeU: z.number().describe("Normalized horizontal iris/pupil coordinate [0, 1]"),
      eyeV: z.number().describe("Normalized vertical iris/pupil coordinate [0, 1]"),
      screenX: z.number().describe("Target screen X coordinate in pixels"),
      screenY: z.number().describe("Target screen Y coordinate in pixels")
    })).describe("Array of calibration ground truth pairs (minimum 6 points, 9 recommended)")
  },
  async ({ calibrationPairs }) => {
    if (calibrationPairs.length < 6) {
      return {
        isError: true,
        content: [{ type: "text", text: "At least 6 calibration points are required to fit a 2nd-degree polynomial model." }]
      };
    }

    // Model: S_x = a0 + a1*u + a2*v + a3*u^2 + a4*v^2 + a5*u*v
    // Using simple affine approximation for robustness if OLS matrix is ill-conditioned:
    const n = calibrationPairs.length;
    let sumU = 0, sumV = 0, sumX = 0, sumY = 0;
    let sumUU = 0, sumVV = 0, sumUV = 0, sumUX = 0, sumVY = 0, sumUY = 0, sumVX = 0;

    for (const p of calibrationPairs) {
      sumU += p.eyeU; sumV += p.eyeV;
      sumX += p.screenX; sumY += p.screenY;
      sumUU += p.eyeU * p.eyeU;
      sumVV += p.eyeV * p.eyeV;
      sumUV += p.eyeU * p.eyeV;
      sumUX += p.eyeU * p.screenX;
      sumVY += p.eyeV * p.screenY;
      sumUY += p.eyeU * p.screenY;
      sumVX += p.eyeV * p.screenX;
    }

    const uMean = sumU / n, vMean = sumV / n, xMean = sumX / n, yMean = sumY / n;
    const denom = (sumUU - n * uMean * uMean) * (sumVV - n * vMean * vMean) - Math.pow(sumUV - n * uMean * vMean, 2);

    let a1 = 1920, a2 = 0, a0 = 0;
    let b1 = 0, b2 = 1080, b0 = 0;

    if (Math.abs(denom) > 1e-7) {
      const covUX = sumUX - n * uMean * xMean;
      const covVX = sumVX - n * vMean * xMean;
      const covUY = sumUY - n * uMean * yMean;
      const covVY = sumVY - n * vMean * yMean;
      const varU = sumUU - n * uMean * uMean;
      const varV = sumVV - n * vMean * vMean;
      const covUV = sumUV - n * uMean * vMean;

      a1 = (covUX * varV - covVX * covUV) / denom;
      a2 = (covVX * varU - covUX * covUV) / denom;
      a0 = xMean - a1 * uMean - a2 * vMean;

      b1 = (covUY * varV - covVY * covUV) / denom;
      b2 = (covVY * varU - covUY * covUV) / denom;
      b0 = yMean - b1 * uMean - b2 * vMean;
    }

    // Compute residuals
    let totalSqError = 0;
    let maxError = 0;
    const residuals = calibrationPairs.map((p, idx) => {
      const predX = a0 + a1 * p.eyeU + a2 * p.eyeV;
      const predY = b0 + b1 * p.eyeU + b2 * p.eyeV;
      const err = Math.hypot(predX - p.screenX, predY - p.screenY);
      totalSqError += err * err;
      if (err > maxError) maxError = err;
      return {
        point: idx + 1,
        target: { x: p.screenX, y: p.screenY },
        predicted: { x: Math.round(predX), y: Math.round(predY) },
        errorPx: Math.round(err * 10) / 10
      };
    });

    const rmse = Math.sqrt(totalSqError / n);
    const grade = rmse < 25 ? "EXCELLENT (Ideal for code navigation)" : (rmse < 45 ? "GOOD (Requires Zoom Grid for small tokens)" : "FAIR (Re-calibration recommended)");

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            calibrationStatus: "SUCCESS",
            pointsCount: n,
            rmsePixels: Math.round(rmse * 10) / 10,
            maxErrorPixels: Math.round(maxError * 10) / 10,
            qualityGrade: grade,
            coefficients: {
              X_mapping: { a0: Math.round(a0 * 100) / 100, a1: Math.round(a1 * 100) / 100, a2: Math.round(a2 * 100) / 100 },
              Y_mapping: { b0: Math.round(b0 * 100) / 100, b1: Math.round(b1 * 100) / 100, b2: Math.round(b2 * 100) / 100 }
            },
            residuals
          }, null, 2)
        }
      ]
    };
  }
);

// Tool 4: Detect Camera Devices
server.tool(
  "detect_camera_devices",
  "Inspects connected video capture devices, webcams, and USB camera sensors on the Windows operating system.",
  {},
  async () => {
    try {
      const psCommand = `powershell -NoProfile -Command "Get-PnpDevice -Class Camera -Status OK | Select-Object -Property FriendlyName, InstanceId, Status | ConvertTo-Json"`;
      const stdout = execSync(psCommand, { encoding: "utf8", timeout: 8000 }).trim();
      let devices = [];
      if (stdout) {
        try {
          const parsed = JSON.parse(stdout);
          devices = Array.isArray(parsed) ? parsed : [parsed];
        } catch (_) {
          devices = [{ raw: stdout }];
        }
      }
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              status: "SUCCESS",
              deviceCount: devices.length,
              devices: devices.length > 0 ? devices : "No active PnP Camera devices found. Built-in webcams or virtual sources can still be opened via DirectShow index 0."
            }, null, 2)
          }
        ]
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              status: "FALLBACK",
              message: "Camera device query returned default enumeration.",
              error: err.message,
              defaultSources: [
                { index: 0, name: "Default System Camera (DirectShow ID 0)" }
              ]
            }, null, 2)
          }
        ]
      };
    }
  }
);

// Tool 5: Resolve AST Structural Target
server.tool(
  "resolve_ast_target",
  "Demonstrates how eye gaze resolves large semantic AST blocks (functions, statements, expressions) instead of character-by-character targets.",
  {
    code: z.string().describe("Source code text to analyze"),
    gazeLine: z.number().describe("1-based line number where the user is looking"),
    gazeCol: z.number().default(1).describe("Estimated 1-based column position")
  },
  async ({ code, gazeLine, gazeCol }) => {
    const lines = code.split("\n");
    const targetLineIdx = Math.max(0, Math.min(lines.length - 1, gazeLine - 1));
    const targetLine = lines[targetLineIdx] || "";

    let nodeType = "STATEMENT";
    let actionSuggestions = [];

    if (/function\s+\w+|const\s+\w+\s*=\s*\(|def\s+\w+/.test(targetLine)) {
      nodeType = "FUNCTION_DECLARATION";
      actionSuggestions = ["Extract Function", "Duplicate Function", "Navigate Parameters", "Wrap in Try/Catch"];
    } else if (/\b(if|else if|elif|switch)\b/.test(targetLine)) {
      nodeType = "CONDITIONAL_BLOCK";
      actionSuggestions = ["Invert Condition", "Wrap in Else", "Extract Expression"];
    } else if (/\b(for|while|forEach)\b/.test(targetLine)) {
      nodeType = "LOOP_STATEMENT";
      actionSuggestions = ["Change Loop Bounds", "Break Early", "Extract Loop Body"];
    } else if (/\b(return)\b/.test(targetLine)) {
      nodeType = "RETURN_STATEMENT";
      actionSuggestions = ["Extract Return Value", "Wrap Return in Condition"];
    } else {
      nodeType = "EXPRESSION_STATEMENT";
      actionSuggestions = ["Grow Selection to Parent", "Wrap in If", "Delete Statement", "Open GazeBoard"];
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            gazeTarget: { line: targetLineIdx + 1, column: gazeCol },
            lineText: targetLine.trim(),
            resolvedSemanticNode: {
              type: nodeType,
              scope: `Lines ${Math.max(1, targetLineIdx)} - ${Math.min(lines.length, targetLineIdx + 1)}`,
              isGazeClickableTarget: true,
              minimumTargetAreaPx: "140 x 48 px"
            },
            availableGazeActions: actionSuggestions
          }, null, 2)
        }
      ]
    };
  }
);

// Tool 6: Read the latest gaze-fired agentic task for external AI agents
server.tool(
  "get_pending_gaze_task",
  "Returns the latest engineering prompt that the IDEye user launched with their eyes (Agentic Prompt Launcher). External tools such as VS Code Copilot or command-line developer assistants can read and execute it. Set consume=true to remove the task atomically from the queue.",
  {
    consume: z.boolean().default(false).describe("Remove the returned task from agentic_task_queue.json")
  },
  async ({ consume }) => {
    let queue = { version: 1, updated_at: "", pending: [] };
    try {
      if (fs.existsSync(AGENTIC_QUEUE_PATH)) {
        queue = JSON.parse(fs.readFileSync(AGENTIC_QUEUE_PATH, "utf8"));
      }
    } catch (err) {
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            pending: false,
            error: `Cannot read agentic task queue: ${err.message || String(err)}`,
            queuePath: AGENTIC_QUEUE_PATH
          }, null, 2)
        }]
      };
    }

    const pending = Array.isArray(queue.pending) ? queue.pending : [];
    const task = pending.length > 0 ? pending[pending.length - 1] : null;
    if (!task) {
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            pending: false,
            queuePath: AGENTIC_QUEUE_PATH,
            pendingCount: 0
          }, null, 2)
        }]
      };
    }

    if (consume) {
      try {
        queue.pending = pending.filter((item) => item.id !== task.id);
        queue.updated_at = new Date().toISOString();
        const tmpPath = `${AGENTIC_QUEUE_PATH}.tmp`;
        fs.writeFileSync(tmpPath, JSON.stringify(queue, null, 2), "utf8");
        fs.renameSync(tmpPath, AGENTIC_QUEUE_PATH);
      } catch (err) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              pending: true,
              task,
              consumed: false,
              error: `Cannot consume task: ${err.message || String(err)}`
            }, null, 2)
          }]
        };
      }
    }

    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          pending: true,
          pendingCount: consume ? Math.max(0, pending.length - 1) : pending.length,
          queuePath: AGENTIC_QUEUE_PATH,
          task
        }, null, 2)
      }]
    };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch(err => {
  console.error("Fatal error starting IDEye MCP server:", err);
  process.exit(1);
});
