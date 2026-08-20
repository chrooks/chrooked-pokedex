# chrooked:zz_levelcap
# Static UI/mechanic mod (not a Ruleset behavior) — always installed by apply.
#
# Party screen hotkey: press F8 to raise every party Pokemon to the current
# level cap (PBExp.currentHardCapLevel, the same badge-based cap that gates
# exp gain). Reuses the Rare Candy path (pbChangeLevel) so stat recalc, move
# learning, and evolutions all run. Eggs, shadow mons, and mons already at
# the cap are skipped. F8 is free: F6/F10 are $DEBUG-only, F2 is controls,
# F3/F4/F5 are item hotkeys.
class PokemonScreen_Scene
  # Chain only when the base method exists — the stub-test harness loads this
  # file against bare stand-in classes with no #update.
  if method_defined?(:update) && !method_defined?(:chrooked_levelcap_update)
    alias chrooked_levelcap_update update
  end

  def update
    chrooked_levelcap_update
    # busy guard: pbDisplay/pbConfirmMessage loops call self.update reentrantly
    return if @chrooked_levelcap_busy || !Input.triggerex?(:F8)
    return if noExp?

    @chrooked_levelcap_busy = true
    begin
      cap = PBExp.currentHardCapLevel
      eligible = $Trainer.party.reject do |p|
        p.isEgg? || (p.isShadow? rescue false) || p.level >= cap
      end
      if eligible.empty?
        pbDisplay(_INTL("Everyone is already at the level cap (Lv. {1}).", cap))
        return
      end
      return if !Kernel.pbConfirmMessage(_INTL("Raise the whole party to the level cap (Lv. {1})?", cap))

      eligible.each { |p| pbChangeLevel(p, cap, self) }
      pbHardRefresh
    ensure
      @chrooked_levelcap_busy = false
    end
  end
end
