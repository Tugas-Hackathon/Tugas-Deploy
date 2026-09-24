import { createConfig, http } from "wagmi"
import { injected } from "wagmi/connectors"
import { defineChain } from "viem"

export const botChainTestnet = defineChain({
  id: 968,
  name: "BOT Chain Testnet",
  nativeCurrency: { name: "tBOT", symbol: "tBOT", decimals: 18 },
  rpcUrls: { default: { http: ["https://rpc.bohr.life"] } },
  blockExplorers: { default: { name: "Blockscout", url: "https://scan.bohr.life" } },
})

export const botChainMainnet = defineChain({
  id: 677,
  name: "BOT Chain",
  nativeCurrency: { name: "BOT", symbol: "BOT", decimals: 18 },
  rpcUrls: { default: { http: ["https://rpc.botchain.ai"] } },
  blockExplorers: { default: { name: "Blockscout", url: "https://scan.botchain.ai" } },
})

export const wagmiConfig = createConfig({
  chains: [botChainTestnet, botChainMainnet],
  connectors: [injected()],
  transports: {
    968: http("https://rpc.bohr.life"),
    677: http("https://rpc.botchain.ai"),
  },
})
