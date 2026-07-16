MONHASH = {
  :BULBASAUR => {
    "Normal Form" => {
      :name => "Bulbasaur",
      :dexnum => 1,
      :Type1 => :GRASS,
      :Type2 => :POISON,
      :BaseStats => [45, 49, 49, 65, 65, 45],
      :Abilities => [:OVERGROW],
      :HiddenAbility => :CHLOROPHYLL,
      :Moveset => [
        [1, :TACKLE],
        [3, :VINEWHIP],
      ],
      :EggMoves => [
        :CURSE,
      ],
    },
  },

  :ABSOL => {
    "Normal Form" => {
      :name => "Absol",
      :dexnum => 359,
      :Type1 => :DARK,
      :Type2 => nil,
      :BaseStats => [65, 130, 60, 75, 60, 75],
      :Abilities => [:PRESSURE, :SUPERLUCK],
      :HiddenAbility => :JUSTIFIED,
      :Moveset => [
        [1, :SCRATCH],
      ],
    },
    "Mega Form" => {
      :name => "Absol",
      :Type1 => :DARK,
      :BaseStats => [65, 150, 60, 115, 60, 115],
      :Abilities => [:MAGICBOUNCE],
    },
  },

  :CHARIZARD => {
    "Normal Form" => {
      :name => "Charizard",
      :dexnum => 6,
      :Type1 => :FIRE,
      :Type2 => :FLYING,
      :BaseStats => [78, 84, 78, 109, 85, 100],
      :Abilities => [:BLAZE],
      :HiddenAbility => :SOLARPOWER,
      :Moveset => [
        [1, :SCRATCH],
      ],
    },
    "Mega X Form" => {
      :name => "Charizard",
      :Type1 => :FIRE,
      :Type2 => :DRAGON,
    },
    "Mega Y Form" => {
      :name => "Charizard",
      :Type1 => :FIRE,
      :Type2 => :FLYING,
    },
  },
}
