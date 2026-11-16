# Revue du 16 novembre 2026

Source de départ : RZU-AdGuard-Home, paquet client corrigé et dossier de développement conservés séparément. Aucune installation ni modification DNS pendant cette revue.

## Modifications

- Identité LiminalGuard : version propre à l’installateur, palette olive/ivoire, porte stylisée et crédits RZU Informatique.
- Contrôle des arguments Bash avant les opérations APT. Une option inconnue ou une valeur manquante ne doit pas provoquer l’installation de dépendances.
- Aide et version accessibles sans droits root. Actions verify/remove reconnues même après une option ; elles n’installent pas de dépendances manquantes.
- Refus précoce d’une installation réelle sans systemd actif.
- Copie profonde du profil pendant la réparation pour ne pas modifier le dictionnaire source en mémoire.
- Nettoyage/restauration prévus aussi pour une interruption clavier pendant l’activation ou la réparation.
- Erreurs de configuration YAML et de marqueur JSON contrôlées ; réponses DNS tronquées signalées sans trace Python brute.
- Version AdGuard et empreintes conservées. Aucun mécanisme de mise à niveau improvisé.

L’affichage minimal et le petit journal technique sont intentionnels. La licence MIT autorise aussi la vente avec conservation du copyright et de la licence. Les identifiants historiques du service et du marqueur restent inchangés.

## Publication

La revue initiale précédait les essais. Les preuves ont depuis été renouvelées pour le script bêta final : voir validation.md. Le paquet client a été généré après leur réussite. La publication reste explicitement expérimentale.

Les seuls contrôles de syntaxe ne prouvent ni l’installation, ni le fonctionnement DNS ; les essais réalisés ensuite sont consignés séparément. Raspberry Pi physique, démarrage après redémarrage et retour des appareils aux DNS habituels restent à valider.

## Contrôles effectués

Syntaxes Bash/Python valides et ShellCheck sans diagnostic. Six tests de revue passent : aide et version, arguments refusés avant dépendances, séparation couleur/JSON, conservation du profil source en mémoire, configuration et marqueur invalides. Aucune installation, activation de service ou modification DNS dans ces tests.

Le logo SVG a été rendu et inspecté. Le ZIP précédent du Bureau reste inchangé ; il ne porte pas encore cette nouvelle identité. Le nouveau paquet a ensuite été généré après les essais complets sous WSL isolé.
