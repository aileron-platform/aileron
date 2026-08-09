(function () {
  const body = document.body;
  const toggle = document.getElementById("mode-toggle");
  const presentationImage = document.getElementById("presentation-image");
  const indicator = document.getElementById("page-indicator");
  const sections = Array.from(document.querySelectorAll(".slide-section"));
  const slideImages = sections.map((section) => section.querySelector("img").getAttribute("src"));
  let currentIndex = 0;
  let indicatorTimer = 0;
  let touchStartX = null;

  function clamp(index) {
    return Math.max(0, Math.min(slideImages.length - 1, index));
  }

  function mostVisibleSlideIndex() {
    let bestIndex = currentIndex;
    let bestVisible = -1;
    const viewportTop = 0;
    const viewportBottom = window.innerHeight;
    sections.forEach((section, index) => {
      const rect = section.getBoundingClientRect();
      const visible = Math.min(rect.bottom, viewportBottom) - Math.max(rect.top, viewportTop);
      if (visible > bestVisible) {
        bestVisible = visible;
        bestIndex = index;
      }
    });
    return clamp(bestIndex);
  }

  function showIndicator() {
    indicator.textContent = `${currentIndex + 1} / ${slideImages.length}`;
    indicator.classList.add("visible");
    window.clearTimeout(indicatorTimer);
    indicatorTimer = window.setTimeout(() => indicator.classList.remove("visible"), 3000);
  }

  function renderPresentationSlide() {
    presentationImage.setAttribute("src", slideImages[currentIndex]);
    showIndicator();
  }

  function enterPresentation() {
    currentIndex = mostVisibleSlideIndex();
    body.classList.remove("reading-mode");
    body.classList.add("presentation-mode");
    toggle.textContent = "閱讀模式";
    toggle.setAttribute("data-i18n-key", "deck.toggleReading");
    renderPresentationSlide();
    if (document.documentElement.requestFullscreen) {
      document.documentElement.requestFullscreen().catch(() => {});
    }
  }

  function exitPresentation() {
    body.classList.remove("presentation-mode");
    body.classList.add("reading-mode");
    toggle.textContent = "簡報模式";
    toggle.setAttribute("data-i18n-key", "deck.togglePresentation");
    const target = sections[currentIndex];
    if (target) {
      window.setTimeout(() => target.scrollIntoView({ block: "start" }), 0);
    }
    if (document.fullscreenElement && document.exitFullscreen) {
      document.exitFullscreen().catch(() => {});
    }
  }

  function goTo(index) {
    currentIndex = clamp(index);
    renderPresentationSlide();
  }

  function next() {
    goTo(currentIndex + 1);
  }

  function previous() {
    goTo(currentIndex - 1);
  }

  toggle.addEventListener("click", () => {
    if (body.classList.contains("presentation-mode")) {
      exitPresentation();
    } else {
      enterPresentation();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (!body.classList.contains("presentation-mode")) {
      return;
    }
    if (["ArrowRight", " ", "PageDown"].includes(event.key)) {
      event.preventDefault();
      next();
    } else if (["ArrowLeft", "PageUp"].includes(event.key)) {
      event.preventDefault();
      previous();
    } else if (event.key === "Home") {
      event.preventDefault();
      goTo(0);
    } else if (event.key === "End") {
      event.preventDefault();
      goTo(slideImages.length - 1);
    } else if (event.key === "Escape") {
      exitPresentation();
    }
  });

  document.addEventListener("click", (event) => {
    if (!body.classList.contains("presentation-mode") || event.target === toggle) {
      return;
    }
    if (event.clientX < window.innerWidth / 2) {
      previous();
    } else {
      next();
    }
  });

  document.addEventListener("touchstart", (event) => {
    if (!body.classList.contains("presentation-mode")) {
      return;
    }
    touchStartX = event.changedTouches[0].clientX;
  }, { passive: true });

  document.addEventListener("touchend", (event) => {
    if (!body.classList.contains("presentation-mode") || touchStartX === null) {
      return;
    }
    const deltaX = event.changedTouches[0].clientX - touchStartX;
    touchStartX = null;
    if (Math.abs(deltaX) < 40) {
      return;
    }
    if (deltaX < 0) {
      next();
    } else {
      previous();
    }
  }, { passive: true });
})();
