import { describe, it, expect } from "vitest";
import { CLASS_VALUES, classOf, classesOf, isMega } from "./dexTags";

describe("classOf", () => {
  it("maps a legendary dex number to Legendary", () => {
    expect(classOf(144)).toBe("Legendary"); // Articuno
    expect(classOf(150)).toBe("Legendary"); // Mewtwo
  });

  it("maps a mythical dex number to Mythical", () => {
    expect(classOf(151)).toBe("Mythical"); // Mew
  });

  it("maps a starter dex number to Starter", () => {
    expect(classOf(1)).toBe("Starter"); // Bulbasaur
  });

  it("maps a fossil dex number to Fossil", () => {
    expect(classOf(142)).toBe("Fossil"); // Aerodactyl
    expect(classOf(567)).toBe("Fossil"); // Archeops
  });

  it("maps Eevee and its evolutions to Eevee Line", () => {
    expect(classOf(133)).toBe("Eevee Line"); // Eevee
    expect(classOf(700)).toBe("Eevee Line"); // Sylveon
  });

  it("maps a pseudo-legendary line to Pseudo-Legendary", () => {
    expect(classOf(147)).toBe("Pseudo-Legendary"); // Dratini
    expect(classOf(149)).toBe("Pseudo-Legendary"); // Dragonite
    expect(classOf(706)).toBe("Pseudo-Legendary"); // Goodra
  });

  it("returns null for a species with no class", () => {
    expect(classOf(16)).toBeNull(); // Pidgey
  });

  it("returns null for a species with no dex number", () => {
    expect(classOf(null)).toBeNull();
  });
});

describe("isMega", () => {
  it("detects Mega forms by the word-boundaried Mega token", () => {
    expect(isMega("Charizard Mega X")).toBe(true);
    expect(isMega("Abomasnow Mega")).toBe(true);
    expect(isMega("Absol Mega Z")).toBe(true);
  });

  it("does not match base species that merely contain the letters", () => {
    expect(isMega("Yanmega")).toBe(false); // lowercase mega in slug-style name
    expect(isMega("Meganium")).toBe(false); // Mega prefix, no word boundary after
    expect(isMega("Charizard")).toBe(false);
  });
});

describe("classesOf", () => {
  it("stacks dex class, Mega, and Fully Evolved for a fully-evolved mega", () => {
    expect(
      classesOf({ dex: 6, name: "Charizard Mega X", fully_evolved: true }),
    ).toEqual(["Starter", "Mega", "Fully Evolved"]);
  });

  it("returns just Mega for a mega whose base has no dex class", () => {
    expect(classesOf({ dex: 460, name: "Abomasnow Mega" })).toEqual(["Mega"]);
  });

  it("adds Fully Evolved for a final form", () => {
    expect(
      classesOf({ dex: 6, name: "Charizard", fully_evolved: true }),
    ).toEqual(["Starter", "Fully Evolved"]);
  });

  it("omits Fully Evolved for a mon that still evolves", () => {
    expect(
      classesOf({ dex: 4, name: "Charmander", fully_evolved: false }),
    ).toEqual(["Starter"]);
  });

  it("returns just the dex class for a non-mega", () => {
    expect(classesOf({ dex: 144, name: "Articuno" })).toEqual(["Legendary"]);
  });

  it("returns nothing for an unclassed non-mega", () => {
    expect(classesOf({ dex: 16, name: "Pidgey" })).toEqual([]);
  });
});

describe("CLASS_VALUES", () => {
  it("lists the filterable classes", () => {
    expect(CLASS_VALUES).toEqual([
      "Legendary",
      "Mythical",
      "Starter",
      "Fossil",
      "Eevee Line",
      "Pseudo-Legendary",
      "Mega",
      "Fully Evolved",
    ]);
  });
});
