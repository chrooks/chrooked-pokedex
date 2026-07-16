MOVEHASH = {
  :TACKLE => {
    :ID => 1,
    :name => "Tackle",
    :desc => "A physical attack in which the user charges and slams into the target.",
    :function => 0x000,
    :type => :NORMAL,
    :category => :physical,
    :basedamage => 40,
    :accuracy => 100,
    :maxpp => 35,
    :target => :SingleNonUser,
    :contact => true,
  },

  :VINEWHIP => {
    :ID => 2,
    :name => "Vine Whip",
    :desc => "The target is struck with slender, whiplike vines.",
    :function => 0x000,
    :type => :GRASS,
    :category => :physical,
    :basedamage => 45,
    :accuracy => 100,
    :maxpp => 25,
    :target => :SingleNonUser,
    :contact => true,
  },
}
