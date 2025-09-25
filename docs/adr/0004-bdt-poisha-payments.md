# 0004. BDT as integer poisha

The shop sells in Bangladesh. Currency is BDT. When prices exist, store them as integer poisha (1 BDT = 100 poisha). Do not use floating point for money. Week 1 has no price tables and no payment code.

A later payment module should depend on a gateway interface with this shape, and nothing else:

- `create_hosted_redirect(order_id, amount_poisha, currency) -> redirect URL` for bKash, SSLCommerz, or another hosted checkout
- `validate(payload) -> result` by calling the gateway API, not by trusting the browser redirect alone

Cash on delivery can be a separate implementation of the same idea (no hosted redirect, a pending collection). There is no Python gateway package in this repo. bKash, SSLCommerz, and COD are Weeks 7–8.
