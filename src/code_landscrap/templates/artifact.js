    (() => {
      const AGGRESSION = {
        elapsed_ms_to_max: 3 * 60 * 1000,
        clicks_to_max: 120,
        scroll_to_max: 9000,
        move_px_to_max: 120000,
      };

      const field = document.querySelector(".temporal-field");
      if (!field) {
        return;
      }
      document.body.classList.add("js-temporal");

      const artifactId = field.dataset.artifactId || "artifact";
      const fragmentTotal = Number(field.dataset.fragmentTotal || "0");
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

      const state = {
        total_elapsed_ms: Number(parsed.total_elapsed_ms) || 0,
        click_count: Number(parsed.click_count) || 0,
        scroll_intensity: Number(parsed.scroll_intensity) || 0,
        move_distance_px: Number(parsed.move_distance_px) || 0,
        hidden_indices: Array.isArray(parsed.hidden_indices)
          ? parsed.hidden_indices.filter((val) => Number.isInteger(val))
          : [],
        pointer_trace: Array.isArray(parsed.pointer_trace) ? parsed.pointer_trace.slice(-24) : [],
        last_seen_ms: Number(parsed.last_seen_ms) || nowMs,
      };

      if (state.last_seen_ms > 0 && nowMs > state.last_seen_ms) {
        const gap = Math.min(nowMs - state.last_seen_ms, 6 * 60 * 60 * 1000);
        state.total_elapsed_ms += gap;
      }

      const root = document.documentElement;
      const residueLayer = document.querySelector(".residue-layer");
      const elapsedClock = document.querySelector('[data-clock="elapsed"]');
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

      function seededIndex(step, length) {
        let hash = 2166136261;
        const seedText = `${artifactId}:${step}`;
        for (let i = 0; i < seedText.length; i += 1) {
          hash ^= seedText.charCodeAt(i);
          hash = Math.imul(hash, 16777619);
        }
        return Math.abs(hash) % Math.max(1, length);
      }

      function totalElapsedNow() {
        return state.total_elapsed_ms + Math.max(0, performance.now() - sessionStartPerf);
      }

      function erosionScore(elapsedMs, clickCount) {
        const fromElapsed = elapsedMs / AGGRESSION.elapsed_ms_to_max;
        const fromClicks = clickCount / AGGRESSION.clicks_to_max;
        const fromScroll = state.scroll_intensity / AGGRESSION.scroll_to_max;
        const fromMoves = state.move_distance_px / AGGRESSION.move_px_to_max;
        return Math.max(0, Math.min(1, fromElapsed + fromClicks + fromScroll + fromMoves));
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
          total_elapsed_ms: Math.round(totalElapsedNow()),
          click_count: state.click_count,
          scroll_intensity: Math.round(state.scroll_intensity),
          move_distance_px: Math.round(state.move_distance_px),
          hidden_indices: state.hidden_indices,
          pointer_trace: state.pointer_trace.slice(-24),
          last_seen_ms: Date.now(),
        };
        storage.setItem(storageKey, JSON.stringify(payload));
      }

      function applyFragmentDecay(score) {
        const targetHidden = Math.floor(score * fragmentTotal * 0.25);
        let step = state.hidden_indices.length;
        while (state.hidden_indices.length < targetHidden && state.hidden_indices.length < fragmentTotal) {
          const candidate = seededIndex(step * 37 + state.click_count, fragmentTotal);
          if (!state.hidden_indices.includes(candidate)) {
            state.hidden_indices.push(candidate);
          }
          step += 1;
        }
        fragments.forEach((frag) => {
          const idx = Number(frag.getAttribute("data-fragment-index"));
          const shouldHide = state.hidden_indices.includes(idx);
          frag.classList.toggle("is-erased", shouldHide);
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
        const score = erosionScore(elapsedMs, state.click_count);
        root.style.setProperty("--erosion", score.toFixed(3));
        root.style.setProperty("--scroll-y", String(window.scrollY));
        if (elapsedClock) {
          elapsedClock.textContent = formatElapsed(elapsedMs);
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
          applyScrollResistance(event);
          applyAtmosphere();
          schedulePersist();
        },
        { passive: false }
      );

      document.addEventListener("pointerdown", (event) => {
        state.click_count += 1;
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
          }
          lastPointer = { x: event.clientX, y: event.clientY };
          lastMoveCapture = nowPerf;
          if (nowPerf % 250 < 32) {
            applyAtmosphere();
            schedulePersist();
          }
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
