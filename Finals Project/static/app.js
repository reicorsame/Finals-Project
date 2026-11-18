(function () {
  var toast = document.getElementById("toast");
  var badge = document.getElementById("cartCount");
  var timer;

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(function () { toast.hidden = true; }, 2200);
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.classList || !form.classList.contains("add-form") || !window.fetch) return;
    event.preventDefault();

    var button = form.querySelector("button");
    var label = button.textContent;
    button.disabled = true;

    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "fetch" },
      credentials: "same-origin"
    })
      .then(function (response) {
        if (!response.ok) throw new Error("request failed");
        return response.json();
      })
      .then(function (data) {
        badge.textContent = data.count;
        badge.hidden = false;
        button.textContent = "Added ✓";
        showToast(data.name + " added to your cart");
        setTimeout(function () { button.textContent = label; button.disabled = false; }, 1200);
      })
      .catch(function () {
        form.submit(); 
      });
  });

  // Back-to-top button.
  var toTop = document.getElementById("toTop");
  if (toTop) {
    var update = function () { toTop.hidden = window.scrollY < 400; };
    window.addEventListener("scroll", update, { passive: true });
    toTop.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
    update();
  }

  // Checkout: show only the fields for the chosen payment method.
  var method = document.getElementById("paymentMethod");
  var payButton = document.getElementById("payButton");
  if (method && payButton) {
    var panels = document.querySelectorAll(".pay-panel");
    var showMethod = function () {
      panels.forEach(function (panel) { panel.hidden = panel.dataset.panel !== method.value; });
      payButton.textContent = "Pay " + payButton.dataset.total + (method.value === "card" ? " by card" : " with GCash");
    };
    method.addEventListener("change", showMethod);
    showMethod();
  }
})();
