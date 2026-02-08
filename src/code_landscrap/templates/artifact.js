(() => {
  const SCHEMA_VERSION = 3;

  const EROSION = {
    // Controls how quickly time alone reaches max erosion (lower = faster).
    // Previously 55s; make it ~3x faster.
    elapsed_ms_to_max: Math.round((55 * 100)),
    relief_half_life_ms: 6500,
    relief_units_to_full: 100,
    relief_units_cap: 180,
    click_relief_units: 16,
    scroll_relief_per_120px: 2.2,
    move_relief_per_px: 1 / 85,
  };

  const field = document.querySelector(".temporal-field");
  if (!field) {
    return;
  }
  document.body.classList.add("js-temporal");

  const artifactId = field.dataset.artifactId || "artifact";
  const storageKey = `landscrap.temporal.${artifactId}`;
  const nowMs = Date.now();
  const memoryStore = {};
  const storage = {
    getItem(key) {
      try {
        return window.localStorage.getItem(key);
      } catch (_err) {
        return Object.prototype.hasOwnProperty.call(memoryStore, key) ? memoryStore[key] : null;
      }
    },
    setItem(key, value) {
      try {
        window.localStorage.setItem(key, value);
      } catch (_err) {
        memoryStore[key] = value;
      }
    },
    removeItem(key) {
      try {
        window.localStorage.removeItem(key);
      } catch (_err) {
        // ignore
      }
      if (Object.prototype.hasOwnProperty.call(memoryStore, key)) {
        delete memoryStore[key];
      }
    },
  };

  const raw = storage.getItem(storageKey);
  let parsed = {};
  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch (_err) {
      parsed = {};
    }
  }
  if (!parsed || parsed.schema_version !== SCHEMA_VERSION) {
    parsed = {};
  }

  const state = {
    total_elapsed_ms: Number(parsed.total_elapsed_ms) || 0,
    click_count: Number(parsed.click_count) || 0,
    scroll_intensity: Number(parsed.scroll_intensity) || 0,
    move_distance_px: Number(parsed.move_distance_px) || 0,
    relief_units: Number(parsed.relief_units) || 0,
    relief_updated_ms: Number(parsed.relief_updated_ms) || nowMs,
    pointer_trace: Array.isArray(parsed.pointer_trace) ? parsed.pointer_trace.slice(-24) : [],
    last_seen_ms: Number(parsed.last_seen_ms) || nowMs,
  };

  const root = document.documentElement;
  const residueLayer = document.querySelector(".residue-layer");
  const elapsedClock = document.querySelector('[data-clock="elapsed"]');
  const reliefClock = document.querySelector('[data-clock="relief"]');
  const clickClock = document.querySelector('[data-clock="clicks"]');
  const scrollClock = document.querySelector('[data-clock="scroll"]');
  const moveClock = document.querySelector('[data-clock="move"]');
  const fragments = Array.from(document.querySelectorAll(".fragment"));
  const durationTargets = Array.from(document.querySelectorAll(".duration-gated"));
  const zones = Array.from(document.querySelectorAll(".resistance-zone"));
  const copyButton = document.querySelector(".code-copy-button");
  const artifactCodeNode = document.querySelector("#artifact-code-block code");
  let sessionStartPerf = performance.now();
  let persistTimer = 0;
  let lastPointer = null;
  let lastMoveCapture = 0;

  function totalElapsedNow() {
    return state.total_elapsed_ms + Math.max(0, performance.now() - sessionStartPerf);
  }

  function clamp01(value) {
    return Math.max(0, Math.min(1, value));
  }

  function decayRelief(now) {
    const dt = Math.max(0, now - state.relief_updated_ms);
    if (dt <= 0) {
      return;
    }
    const halfLife = Math.max(250, EROSION.relief_half_life_ms);
    const decayFactor = Math.pow(0.5, dt / halfLife);
    state.relief_units *= decayFactor;
    state.relief_updated_ms = now;
  }

  function addRelief(units) {
    if (!Number.isFinite(units) || units <= 0) {
      return;
    }
    const now = Date.now();
    decayRelief(now);
    state.relief_units = Math.min(EROSION.relief_units_cap, state.relief_units + units);
  }

  function erosionScore(elapsedMs) {
    decayRelief(Date.now());
    const timePressure = clamp01(elapsedMs / EROSION.elapsed_ms_to_max);
    const relief = clamp01(state.relief_units / EROSION.relief_units_to_full);
    return clamp01(timePressure - relief);
  }

      function formatElapsed(ms) {
        const totalSeconds = Math.max(0, Math.floor(ms / 1000));
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
      }

      function formatPixels(px) {
        if (px >= 1000) {
          return `${(px / 1000).toFixed(1)}k px`;
        }
        return `${Math.floor(px)} px`;
      }

  function schedulePersist() {
    if (persistTimer) {
      return;
    }
    persistTimer = window.setTimeout(() => {
      persistTimer = 0;
      persistState();
    }, 300);
  }

  function persistState() {
    const payload = {
      schema_version: SCHEMA_VERSION,
      total_elapsed_ms: Math.round(totalElapsedNow()),
      click_count: state.click_count,
      scroll_intensity: Math.round(state.scroll_intensity),
      move_distance_px: Math.round(state.move_distance_px),
      relief_units: state.relief_units,
      relief_updated_ms: state.relief_updated_ms,
      pointer_trace: state.pointer_trace.slice(-24),
      last_seen_ms: Date.now(),
    };
    storage.setItem(storageKey, JSON.stringify(payload));
  }

  function fragmentSeed(idx) {
    let hash = 2166136261;
    const seedText = `${artifactId}:frag:${idx}`;
    for (let i = 0; i < seedText.length; i += 1) {
      hash ^= seedText.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0) / 4294967295;
  }

  const fragmentPlans = fragments.map((frag) => {
    const idx = Number(frag.getAttribute("data-fragment-index"));
    const seed = fragmentSeed(idx);
    const start = seed * 0.8;
    const span = 0.3 - (seed * 0.1);
    return { frag, start, span };
  });

  function smoothstep(t) {
    const x = clamp01(t);
    return x * x * (3 - (2 * x));
  }

  function applyFragmentDecay(score) {
    fragmentPlans.forEach(({ frag, start, span }) => {
      const raw = span > 0 ? (score - start) / span : 1;
      const local = smoothstep(raw);
      frag.style.setProperty("--fragment-erosion", local.toFixed(3));
      frag.classList.toggle("is-erased", local >= 0.999);
    });
  }

      function renderPointerTrace() {
        if (!residueLayer) {
          return;
        }
        residueLayer.innerHTML = "";
        state.pointer_trace.forEach((point, idx) => {
          const dot = document.createElement("span");
          dot.className = "residue-dot";
          dot.style.left = `${Math.round(point.x * 100)}vw`;
          dot.style.top = `${Math.round(point.y * 100)}vh`;
          dot.style.opacity = `${Math.max(0.05, (idx + 2) / (state.pointer_trace.length * 5))}`;
          residueLayer.appendChild(dot);
        });
      }

      function applyAtmosphere() {
        const elapsedMs = totalElapsedNow();
        const score = erosionScore(elapsedMs);
        const relief = clamp01(state.relief_units / EROSION.relief_units_to_full);
        root.style.setProperty("--erosion", score.toFixed(3));
        root.style.setProperty("--scroll-y", String(window.scrollY));
        if (elapsedClock) {
          elapsedClock.textContent = formatElapsed(elapsedMs);
        }
        if (reliefClock) {
          reliefClock.textContent = `${Math.round(relief * 100)}%`;
        }
        if (clickClock) {
          clickClock.textContent = String(state.click_count);
        }
        if (scrollClock) {
          scrollClock.textContent = String(Math.round(state.scroll_intensity));
        }
        if (moveClock) {
          moveClock.textContent = formatPixels(state.move_distance_px);
        }
        applyFragmentDecay(score);
      }

      const revealState = new WeakMap();
      if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver(
          (entries) => {
            const nowPerf = performance.now();
            entries.forEach((entry) => {
              const current = revealState.get(entry.target) || { visible_ms: 0, entered_at: 0, visible: false };
              if (entry.isIntersecting) {
                if (!current.visible) {
                  current.entered_at = nowPerf;
                  current.visible = true;
                }
              } else if (current.visible) {
                current.visible_ms += Math.max(0, nowPerf - current.entered_at);
                current.entered_at = 0;
                current.visible = false;
              }
              revealState.set(entry.target, current);
            });
          },
          { threshold: 0.1 }
        );
        durationTargets.forEach((target) => observer.observe(target));
      } else {
        const startPerf = performance.now();
        durationTargets.forEach((target) => {
          revealState.set(target, { visible_ms: 0, entered_at: startPerf, visible: true });
        });
      }

      function tickReveals(nowPerf) {
        durationTargets.forEach((target) => {
          if (target.classList.contains("is-revealed")) {
            return;
          }
          const stateForTarget = revealState.get(target);
          if (!stateForTarget) {
            return;
          }
          const configured = Number(target.getAttribute("data-reveal-after")) || 5;
          const afterSec = Math.min(30, configured);
          const activeMs = stateForTarget.visible ? Math.max(0, nowPerf - stateForTarget.entered_at) : 0;
          const totalVisibleMs = stateForTarget.visible_ms + activeMs;
          if (totalVisibleMs >= afterSec * 1000) {
            target.classList.add("is-revealed");
          }
        });
      }

      function applyScrollResistance(event) {
        const centerY = window.innerHeight * 0.5;
        const active = zones.find((zone) => {
          const rect = zone.getBoundingClientRect();
          return rect.top <= centerY && rect.bottom >= centerY;
        });
        if (!active) {
          return;
        }
        const resistance = Number(active.getAttribute("data-resistance")) || 0;
        if (resistance <= 0) {
          return;
        }
        event.preventDefault();
        window.scrollBy({ top: event.deltaY * (1 - resistance), behavior: "auto" });
      }

      fragments.forEach((frag) => {
        const setActive = (active) => frag.classList.toggle("is-active", active);
        frag.addEventListener("mouseenter", () => setActive(true));
        frag.addEventListener("mouseleave", () => setActive(false));
        frag.addEventListener("focusin", () => setActive(true));
        frag.addEventListener("focusout", () => setActive(false));
        frag.addEventListener("click", () => setActive(!frag.classList.contains("is-active")));

        const driftRate = Number(frag.getAttribute("data-drift")) || 0.02;
        frag.style.setProperty("--drift-rate", driftRate.toFixed(3));
      });

      async function copyText(text) {
        if (!text) {
          return false;
        }

        if (navigator.clipboard && window.isSecureContext) {
          try {
            await navigator.clipboard.writeText(text);
            return true;
          } catch (_err) {
            // Fall through to the textarea fallback.
          }
        }

        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.setAttribute("readonly", "");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        textarea.style.pointerEvents = "none";
        document.body.appendChild(textarea);
        textarea.select();

        let copied = false;
        try {
          copied = document.execCommand("copy");
        } catch (_err) {
          copied = false;
        }
        document.body.removeChild(textarea);
        return copied;
      }

      let copyFlashTimer = 0;
      if (copyButton && artifactCodeNode) {
        copyButton.addEventListener("click", async (event) => {
          event.preventDefault();
          event.stopPropagation();

          const source = artifactCodeNode.textContent || "";
          const ok = await copyText(source);

          if (copyFlashTimer) {
            window.clearTimeout(copyFlashTimer);
            copyFlashTimer = 0;
          }

          copyButton.classList.remove("is-copied", "is-failed");
          if (ok) {
            copyButton.textContent = "✓";
            copyButton.classList.add("is-copied");
            copyButton.setAttribute("aria-label", "Copied");
            copyButton.setAttribute("title", "Copied");
          } else {
            copyButton.textContent = "!";
            copyButton.classList.add("is-failed");
            copyButton.setAttribute("aria-label", "Copy failed");
            copyButton.setAttribute("title", "Copy failed");
          }

          copyFlashTimer = window.setTimeout(() => {
            copyButton.textContent = "⧉";
            copyButton.classList.remove("is-copied", "is-failed");
            copyButton.setAttribute("aria-label", "Copy artifact code");
            copyButton.setAttribute("title", "Copy code");
          }, 1200);
        });
      }

      document.addEventListener(
        "wheel",
        (event) => {
          state.scroll_intensity += Math.abs(event.deltaY) + (Math.abs(event.deltaX) * 0.35);
          addRelief((Math.abs(event.deltaY) + (Math.abs(event.deltaX) * 0.35)) / 120 * EROSION.scroll_relief_per_120px);
          applyScrollResistance(event);
          applyAtmosphere();
          schedulePersist();
        },
        { passive: false }
      );

      document.addEventListener("pointerdown", (event) => {
        state.click_count += 1;
        addRelief(EROSION.click_relief_units);
        lastPointer = { x: event.clientX, y: event.clientY };
        const width = Math.max(1, window.innerWidth);
        const height = Math.max(1, window.innerHeight);
        state.pointer_trace.push({
          x: Math.max(0, Math.min(1, event.clientX / width)),
          y: Math.max(0, Math.min(1, event.clientY / height)),
          t: Date.now(),
        });
        state.pointer_trace = state.pointer_trace.slice(-24);
        renderPointerTrace();
        applyAtmosphere();
        schedulePersist();
      });

      document.addEventListener(
        "pointermove",
        (event) => {
          if (event.pointerType && event.pointerType !== "mouse") {
            return;
          }
          const nowPerf = performance.now();
          if (nowPerf - lastMoveCapture < 32) {
            return;
          }
          if (lastPointer) {
            const dx = event.clientX - lastPointer.x;
            const dy = event.clientY - lastPointer.y;
            const dist = Math.sqrt((dx * dx) + (dy * dy));
            state.move_distance_px += dist;
            addRelief(dist * EROSION.move_relief_per_px);
          }
          lastPointer = { x: event.clientX, y: event.clientY };
          lastMoveCapture = nowPerf;
          schedulePersist();
        },
        { passive: true }
      );

      let minuteTimer = window.setInterval(() => {
        document.body.classList.toggle("minute-shift");
      }, 60000);

      const onceKey = `landscrap.once.${artifactId}`;
      if (!sessionStorage.getItem(onceKey)) {
        sessionStorage.setItem(onceKey, "seen");
        document.body.classList.add("minute-shift");
      }

      function animationLoop(nowPerf) {
        root.style.setProperty("--fast-wave", String(Math.sin(nowPerf / 1400)));
        tickReveals(nowPerf);
        applyAtmosphere();
        requestAnimationFrame(animationLoop);
      }

      function shutdown() {
        window.clearInterval(minuteTimer);
        persistState();
      }

      renderPointerTrace();
      applyAtmosphere();
      window.addEventListener("scroll", applyAtmosphere, { passive: true });
      window.addEventListener("beforeunload", shutdown);
      window.addEventListener("pagehide", shutdown);
      field.addEventListener("mouseleave", schedulePersist);
      requestAnimationFrame(animationLoop);
    })();
