import { ClobClient, OrderType, Side } from "@polymarket/clob-client";
import { Wallet } from "@ethersproject/wallet";
import { SignatureType } from "@polymarket/order-utils";

const readStdin = async () => {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8").trim();
};

const resolveSignatureType = (value) => {
  if (typeof value === "number") {
    return value;
  }
  const normalized = String(value || "EOA").toUpperCase();
  if (normalized === "POLY_GNOSIS_SAFE") {
    return SignatureType.POLY_GNOSIS_SAFE;
  }
  if (normalized === "POLY_PROXY") {
    return SignatureType.POLY_PROXY;
  }
  return SignatureType.EOA;
};

const resolveOrderType = (value) => {
  const normalized = String(value || "FOK").toUpperCase();
  if (normalized === "FAK") {
    return OrderType.FAK;
  }
  if (normalized === "GTC") {
    return OrderType.GTC;
  }
  if (normalized === "GTD") {
    return OrderType.GTD;
  }
  return OrderType.FOK;
};

const resolveSide = (value) => {
  const normalized = String(value || "BUY").toUpperCase();
  if (normalized === "SELL") {
    return Side.SELL;
  }
  return Side.BUY;
};

const ensureNumber = (value, field) => {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    throw new Error(`Invalid ${field}: ${value}`);
  }
  return num;
};

const createAuthedClient = async ({ host, chainId, privateKey, signatureType, funderAddress }) => {
  if (!privateKey) {
    throw new Error("Missing privateKey for CLOB client");
  }
  if (!host) {
    throw new Error("Missing host for CLOB client");
  }
  if (!chainId) {
    throw new Error("Missing chainId for CLOB client");
  }

  const wallet = new Wallet(privateKey);
  const sigType = resolveSignatureType(signatureType);

  const client = new ClobClient(
    host,
    chainId,
    wallet,
    undefined,
    sigType,
    funderAddress || undefined
  );
  const creds = await client.createOrDeriveApiKey();

  return new ClobClient(
    host,
    chainId,
    wallet,
    creds,
    sigType,
    funderAddress || undefined
  );
};

const handlePostOrder = async (payload) => {
  const order = payload.order || {};
  const tokenID = order.tokenID || order.tokenId;
  if (!tokenID) {
    throw new Error("Missing tokenID in order");
  }

  const client = await createAuthedClient(payload);
  const userMarketOrder = {
    tokenID,
    side: resolveSide(order.side),
    amount: ensureNumber(order.amount, "amount"),
  };

  if (order.price !== undefined && order.price !== null) {
    userMarketOrder.price = ensureNumber(order.price, "price");
  }

  const signedOrder = await client.createMarketOrder(userMarketOrder);
  const response = await client.postOrder(signedOrder, resolveOrderType(payload.orderType));

  const isObject = response && typeof response === "object";
  const hasOrderId =
    (isObject && (response.orderID || response.orderId || response.id || response.order_id)) ||
    (isObject &&
      response.data &&
      (response.data.orderID ||
        response.data.orderId ||
        response.data.id ||
        response.data.order_id));
  const errorMessage =
    (isObject && (response.error || response.message || response.errorMsg)) ||
    (isObject && response.data && (response.data.error || response.data.message || response.data.errorMsg));
  const success = (isObject && response.success === true) || Boolean(hasOrderId);

  if (success) {
    return { success: true, data: response };
  }

  return { success: false, error: errorMessage || "Order rejected by CLOB", data: response };
};

const main = async () => {
  const rawInput = await readStdin();
  if (!rawInput) {
    throw new Error("No input provided to CLOB bridge");
  }

  const { action, payload } = JSON.parse(rawInput);
  if (!action) {
    throw new Error("Missing action for CLOB bridge");
  }

  if (action === "post_order") {
    return await handlePostOrder(payload || {});
  }

  throw new Error(`Unsupported action: ${action}`);
};

try {
  const result = await main();
  process.stdout.write(JSON.stringify(result));
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(message);
  process.exit(1);
}
