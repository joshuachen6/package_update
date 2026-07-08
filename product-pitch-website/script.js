const steps = Array.from(document.querySelectorAll(".flow-step"));

if (steps.length > 0) {
  let current = 0;

  setInterval(() => {
    steps[current].classList.remove("active");
    current = (current + 1) % steps.length;
    steps[current].classList.add("active");
  }, 1800);
}

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const id = link.getAttribute("href");
    const target = id ? document.querySelector(id) : null;

    if (target) {
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
});
