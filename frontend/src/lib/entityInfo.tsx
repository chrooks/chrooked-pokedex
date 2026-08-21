/* App-wide lookup of full Move / Ability records by display name, for the
   hover cards. Read-only, provided once in App from the already-loaded
   resources; consumers get `undefined` for unknown names and render nothing.
   Keys are lowercased so "coil" and "Coil" resolve alike. */

import { createContext, useContext, useMemo, type ReactNode } from "react";
import type { Ability, Move } from "../types";

interface EntityInfo {
  moveByName: ReadonlyMap<string, Move>;
  abilityByName: ReadonlyMap<string, Ability>;
}

const EMPTY: EntityInfo = { moveByName: new Map(), abilityByName: new Map() };

const EntityInfoContext = createContext<EntityInfo>(EMPTY);

export function EntityInfoProvider({
  moves,
  abilities,
  children,
}: {
  moves: Move[] | null;
  abilities: Ability[] | null;
  children: ReactNode;
}) {
  const value = useMemo<EntityInfo>(
    () => ({
      moveByName: new Map((moves ?? []).map((m) => [m.name.toLowerCase(), m])),
      abilityByName: new Map((abilities ?? []).map((a) => [a.name.toLowerCase(), a])),
    }),
    [moves, abilities],
  );
  return <EntityInfoContext.Provider value={value}>{children}</EntityInfoContext.Provider>;
}

export function useMoveInfo(name: string | null): Move | undefined {
  const { moveByName } = useContext(EntityInfoContext);
  return name ? moveByName.get(name.toLowerCase()) : undefined;
}

export function useAbilityInfo(name: string | null): Ability | undefined {
  const { abilityByName } = useContext(EntityInfoContext);
  return name ? abilityByName.get(name.toLowerCase()) : undefined;
}
