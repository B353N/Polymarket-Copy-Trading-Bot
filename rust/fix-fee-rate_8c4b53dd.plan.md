---
name: fix-fee-rate
overview: Create an isolated repo copy, then update order signing to use the market’s taker fee rate instead of hard-coded 0 so orders stop failing with "invalid fee rate".
todos:
  - id: copy-repo
    content: Create sibling repo copy for sandbox work
    status: completed
  - id: fee-rate-cache
    content: Add fee-rate cache + fetch via /fee-rate endpoint
    status: in_progress
  - id: signing-update
    content: Use feeRateBps from args/cache in order signing
    status: pending
  - id: verify
    content: Build or check for errors in sandbox
    status: pending
---

# Fix fee rate in sandbox

## Scope
- Work in a **separate copy** of the repo (sibling directory) so the running bot is untouched.
- Update order signing to use the market’s actual taker fee rate from CLOB API.

## Key files
- `[/Users/b353n/Projects/Polymarket-Copy-Trading-Bot/rust/src/lib.rs](/Users/b353n/Projects/Polymarket-Copy-Trading-Bot/rust/src/lib.rs)` (order signing / feeRateBps hardcoded)
- `[/Users/b353n/Projects/Polymarket-Copy-Trading-Bot/rust/src/market_cache.rs](/Users/b353n/Projects/Polymarket-Copy-Trading-Bot/rust/src/market_cache.rs)` (add fee-rate cache helper)
- `[/Users/b353n/Projects/Polymarket-Copy-Trading-Bot/rust/src/main.rs](/Users/b353n/Projects/Polymarket-Copy-Trading-Bot/rust/src/main.rs)` (no behavioral change expected; verify OrderArgs still pass None)

## Plan
1. Create a sibling copy of the repo and work only there.
2. Replace the hard-coded `feeRateBps` value in `order_typed_data` with a formatted value from `OrderData` and pass the computed fee through `OrderData` (instead of `FEE_RATE_ZERO`).
3. Add a small cache + fetch in `market_cache` to retrieve `fee_rate_bps` from `GET /fee-rate?token_id=...` (CLOB API), with in-memory caching to avoid repeated calls.
4. In `RustClobClient::create_order`, resolve fee rate as:
   - `args.fee_rate_bps` if provided, otherwise
   - cached/fetched fee rate for the token.
   - If fetching fails, return a descriptive error (so we don’t sign invalid orders).
5. Smoke-check compilation and update any tests if needed.

## Notes (code context)
Currently `feeRateBps` is hardcoded to `"0"` in typed data and `OrderData`:
```
687:725:/Users/b353n/Projects/Polymarket-Copy-Trading-Bot/rust/src/lib.rs
fn order_typed_data(chain_id: u64, exchange: &str, data: &OrderData) -> Result<TypedData> {
    let json_str = format!(
        /* ... */
        r#""message":{{...,"feeRateBps":"0",...}}}}"#
    );
    /* ... */
}
```
We’ll replace this with `data.fee_rate_bps` and wire that through `create_order`.