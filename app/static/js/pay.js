(function () {
  "use strict";

  var button = document.getElementById("pay-now");
  if (!button) {
    return;
  }

  var orderId = button.getAttribute("data-order-id") || "";
  var errorBox = document.getElementById("pay-error");

  function currentAccess() {
    var params = new URLSearchParams(window.location.search);
    var token = params.get("token");
    return token
      ? { token: token }
      : { exp: params.get("exp"), sig: params.get("sig") };
  }

  function showError(message) {
    if (errorBox) {
      errorBox.textContent = message;
      errorBox.hidden = false;
    }
    button.disabled = false;
  }

  function readError(response) {
    return response
      .json()
      .catch(function () {
        return {};
      })
      .then(function (payload) {
        throw new Error(
          (payload && payload.error && payload.error.message) ||
            "We could not start the payment. Please try again.",
        );
      });
  }

  function confirmPayment(response) {
    fetch("/api/payments/verify", {
      method: "POST",
      headers: { "content-type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(Object.assign(currentAccess(), {
        orderId: orderId,
        razorpayOrderId: response.razorpay_order_id,
        razorpayPaymentId: response.razorpay_payment_id,
        signature: response.razorpay_signature,
      })),
    })
      .then(function (verified) {
        if (!verified.ok) {
          return readError(verified);
        }
        window.location.replace(window.location.pathname + window.location.search);
      })
      .catch(function (error) {
        showError(error.message || "We could not confirm this payment. Please try again.");
      });
  }

  button.addEventListener("click", function () {
    button.disabled = true;
    if (errorBox) {
      errorBox.hidden = true;
    }
    fetch("/api/payments/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(Object.assign(currentAccess(), { orderId: orderId })),
    })
      .then(function (response) {
        if (!response.ok) {
          return readError(response);
        }
        return response.json();
      })
      .then(function (session) {
        var checkout = new window.Razorpay({
          key: session.keyId,
          order_id: session.razorpayOrderId,
          amount: session.amountMinor,
          currency: session.currency,
          name: "Luit & Loom",
          description: "Handwoven Assamese textiles",
          handler: confirmPayment,
          modal: {
            ondismiss: function () {
              button.disabled = false;
            },
          },
        });
        checkout.open();
      })
      .catch(function (error) {
        showError(error.message || "Payments are unavailable right now.");
      });
  });
})();
