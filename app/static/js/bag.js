(function () {
  "use strict";

  var BAG_KEY = "luit-loom-bag-v1";
  var MAX_LINES = 20;
  var MAX_QUANTITY = 10;

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character];
    });
  }

  function readBag() {
    try {
      var raw = JSON.parse(window.localStorage.getItem(BAG_KEY) || "[]");
      if (!Array.isArray(raw)) return [];
      var seen = {};
      var bag = [];
      raw.forEach(function (entry) {
        if (!entry || typeof entry.v !== "string" || !/^[0-9a-f-]{36}$/i.test(entry.v)) return;
        var quantity = Math.floor(Number(entry.q));
        if (!isFinite(quantity)) return;
        quantity = Math.min(MAX_QUANTITY, Math.max(1, quantity));
        var key = entry.v.toLowerCase();
        if (seen[key]) {
          seen[key].q = Math.min(MAX_QUANTITY, seen[key].q + quantity);
          return;
        }
        var line = { v: entry.v, q: quantity };
        seen[key] = line;
        bag.push(line);
      });
      return bag.slice(0, MAX_LINES);
    } catch (error) {
      return [];
    }
  }

  function saveBag(bag) {
    try {
      window.localStorage.setItem(BAG_KEY, JSON.stringify(bag));
    } catch (error) {
      /* storage unavailable; bag stays in memory for this visit */
    }
    updateCount();
  }

  function bagCount(bag) {
    return bag.reduce(function (sum, line) { return sum + line.q; }, 0);
  }

  function updateCount() {
    var count = bagCount(readBag());
    document.querySelectorAll("[data-bag-count]").forEach(function (node) {
      node.textContent = String(count);
    });
  }

  function postQuote(bag) {
    return window.fetch("/api/cart/quote", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        items: bag.map(function (line) {
          return { variantId: line.v, quantity: line.q };
        }),
      }),
    }).then(function (response) {
      if (!response.ok) {
        throw new Error("quote failed");
      }
      return response.json();
    });
  }

  function renderLines(quote) {
    var rows = quote.lines.map(function (line) {
      var action = line.available
        ? '<button class="text-link" type="button" data-remove="' + escapeHtml(line.variantId) + '">Remove</button>'
        : '<p class="availability is-unavailable">Just sold out</p>';
      return '<tr class="bag-table__item"><th colspan="3">' + escapeHtml(line.productTitle) +
        '<span class="bag-table__variant">' + escapeHtml(line.variantTitle) + '</span></th></tr>' +
        '<tr class="bag-table__line"><td>' + line.quantity + ' \u00d7 ' + escapeHtml(line.unitPriceFormatted) +
        '</td><td class="is-numeric">' + escapeHtml(line.lineTotalFormatted) +
        '</td><td class="bag-table__action">' + action + '</td></tr>';
    }).join("");
    return '<table class="bag-table bag-table--stacked"><tbody>' + rows + '</tbody></table>' +
      '<dl class="summary-totals"><div><dt>Subtotal</dt><dd>' +
      escapeHtml(quote.subtotalFormatted) + "</dd></div></dl>";
  }

  function renderCart() {
    var root = document.getElementById("cart-root");
    if (!root) return;
    var bag = readBag();
    if (!bag.length) {
      root.innerHTML = '<div class="empty-state"><p>Your bag is empty.</p>' +
        '<a class="button button--secondary" href="/shop">Browse all weaves</a></div>';
      return;
    }
    root.innerHTML = '<p class="empty-state">Opening your bag…</p>';
    postQuote(bag).then(function (quote) {
      root.innerHTML =
        renderLines(quote) +
        '<div class="action-row">' +
        (quote.allAvailable
          ? '<a class="button" href="/checkout">Continue to checkout</a>'
          : '<p class="form-alert" role="alert">Remove sold-out weaves to continue.</p>') +
        '<a class="button button--secondary" href="/shop">Keep browsing</a></div>';
      bindRemoveButtons(root);
    }).catch(function () {
      root.innerHTML = '<p class="form-alert" role="alert">We could not price your bag. Please refresh.</p>';
    });
  }

  function bindRemoveButtons(scope) {
    scope.querySelectorAll("[data-remove]").forEach(function (button) {
      button.addEventListener("click", function () {
        saveBag(
          readBag().filter(function (line) {
            return line.v.toLowerCase() !== button.getAttribute("data-remove").toLowerCase();
          })
        );
        renderCart();
      });
    });
  }

  function renderCheckoutSummary() {
    var itemsField = document.getElementById("checkout-items");
    var summary = document.getElementById("checkout-summary");
    if (!itemsField || !summary) return;
    var form = itemsField.closest("form");
    var bag = readBag();
    if (!bag.length) {
      form.innerHTML = '<div class="empty-state"><p>Your bag is empty.</p>' +
        '<a class="button button--secondary" href="/shop">Browse all weaves</a></div>';
      return;
    }
    itemsField.setAttribute("value", JSON.stringify(
      bag.map(function (line) { return { variantId: line.v, quantity: line.q }; })
    ));
    summary.innerHTML = '<p class="empty-state">Reviewing your bag…</p>';
    postQuote(bag).then(function (quote) {
      summary.innerHTML = renderLines(quote) +
        (quote.allAvailable
          ? ""
          : '<p class="form-alert" role="alert">A weave just sold out. Return to your <a href="/cart">bag</a>.</p>');
    }).catch(function () {
      summary.innerHTML = '<p class="form-alert" role="alert">We could not price your bag. Please refresh.</p>';
    });
  }

  function bindAddToBagForms() {
    document.querySelectorAll("form[data-add-to-bag]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var select = form.querySelector('select[name="variant"]');
        var quantityInput = form.querySelector('input[name="quantity"]');
        if (!select || !select.value) return;
        var quantity = Math.floor(Number(quantityInput ? quantityInput.value : 1)) || 1;
        quantity = Math.min(MAX_QUANTITY, Math.max(1, quantity));
        var bag = readBag();
        var key = select.value.toLowerCase();
        var existing = null;
        for (var index = 0; index < bag.length; index += 1) {
          if (bag[index].v.toLowerCase() === key) {
            existing = bag[index];
            break;
          }
        }
        if (existing) {
          existing.q = Math.min(MAX_QUANTITY, existing.q + quantity);
        } else {
          bag.push({ v: select.value, q: quantity });
        }
        saveBag(bag.slice(0, MAX_LINES));
        var note = form.querySelector(".add-to-bag__note");
        if (note) {
          note.hidden = false;
          note.textContent = "Added to bag. View your bag when you are ready.";
        }
      });
    });
  }

  function init() {
    updateCount();
    bindAddToBagForms();
    renderCart();
    renderCheckoutSummary();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
