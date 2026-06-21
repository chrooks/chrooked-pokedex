# chrooked:obfuscate
# Obfuscate: Normal-type moves become DARK-type and gain 1.2x power (a custom -ate clone).
# Seam: PokeBattle_Move#pbModifyType (type swap + @powerboost) + #pbModifyDamage (the 1.2x —
# vanilla applies it only to the 4 stock -ate abilities, so our custom ability applies its own).
# Ruby 1.8: alias_method chaining (NO prepend / NO TracePoint); deferred install on Graphics.update.

unless defined?($chrooked_log) && $chrooked_log
  $chrooked_log = lambda do |msg|
    begin
      d = File.expand_path(File.dirname(__FILE__))
      File.open(File.join(d, "chrooked_load.log"), "a") { |f| f.puts(msg) }
    rescue Exception
    end
  end
end

def chrooked_install_obfuscate
  return if $chrooked_obfuscate_installed
  return unless defined?(PokeBattle_Move)
  im = PokeBattle_Move.instance_methods.map { |m| m.to_s }
  return unless im.include?("pbModifyType") && im.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyType_chrooked_obfuscate_orig")
      alias_method :pbModifyType_chrooked_obfuscate_orig, :pbModifyType
      def pbModifyType(type, attacker, opponent)
        type = pbModifyType_chrooked_obfuscate_orig(type, attacker, opponent)
        if type>=0 && isConst?(type,PBTypes,:NORMAL) && (attacker.hasWorkingAbility(:OBFUSCATE) rescue false) && hasConst?(PBTypes,:DARK)
          type = getConst(PBTypes,:DARK)
          @powerboost = true
        end
        type
      end
    end
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_obfuscate_orig")
      alias_method :pbModifyDamage_chrooked_obfuscate_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        m = pbModifyDamage_chrooked_obfuscate_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:OBFUSCATE) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_ab && @powerboost
          m = (m*1.2).round
          ($chrooked_log.call("[chrooked:obfuscate] OBS move=#{movename} ability=true converted=DARK boosted=true") rescue nil)
        else
          ($chrooked_log.call("[chrooked:obfuscate] OBS move=#{movename} ability=#{is_ab} converted=none boosted=false") rescue nil)
        end
        m
      end
    end
  end
  $chrooked_obfuscate_installed = true
  ($chrooked_log.call("[chrooked:obfuscate] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map{|m|m.to_s}.include?("pbModifyType")
  chrooked_install_obfuscate
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_obfuscate_orig)
      alias_method :update_chrooked_obfuscate_orig, :update
      def update
        chrooked_install_obfuscate if !$chrooked_obfuscate_installed && defined?(PokeBattle_Move)
        update_chrooked_obfuscate_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:obfuscate] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:obfuscate] ERROR: PokeBattle_Move/Graphics missing at load") rescue nil)
end
