# Validation — 0.1.0-beta.1

Vérifications du 16 novembre 2026. Elles décrivent cette version ; elles ne garantissent pas l’absence de défauts sur tous les appareils.

## Essais réussis

- Syntaxes Bash et Python valides ; ShellCheck sans diagnostic.
- Six tests de revue : aide/version sans installation, arguments invalides refusés avant APT, sorties couleur/JSON, profil source conservé, configurations et marqueurs invalides signalés.
- Vingt et un tests d’intégration dans un espace réseau privé : installation, résolution DNS TCP/UDP, blocage, interface protégée, réparation, retrait/reprise, refus des ports occupés, des installations étrangères, des binaires altérés et des listes absentes.
- Vrais binaires officiels amd64, ARMv7, ARM64 et ARMv6 exécutés. Les variantes ARM ont été lancées sous QEMU.
- Service systemd temporaire isolé : installation, vérification, réparation, retrait et réinstallation.
- Session interactive réelle en pseudo-terminal : un seul mot de passe, masqué, conservé intégralement ; couleurs et présentation sur 40 colonnes.
- Sept tests de saisie : UTF-8, collage, retour arrière, dépassement de taille, absence d’écho en clair et restauration du terminal après Ctrl+C ou SIGTERM.
- Résolveurs HTTPS réels AdGuard DNS et Quad9 : résolution et contrôle parental vérifiés sur loopback, ports de test dédiés.
- Empreintes des preuves concordantes avec le script ; paquet client créé et contrôlé par CRC et SHA-256.

Le DNS de l’hôte n’a pas été modifié. Les tests systemd emploient un service temporaire et un espace réseau privé. Les comptes et mots de passe des tests sont temporaires et ne sont pas des identifiants de production.

Les fichiers JSON dans `preuves/` contiennent l’empreinte du script réellement testé. Le paquetage refuse une preuve manquante, échouée ou périmée.

## Environnement et limites

Ubuntu sous WSL2, systemd actif, Python 3, PyYAML, bcrypt et QEMU. Ce n’est pas une carte Raspberry physique. Restent à vérifier sur matériel : installation Raspberry Pi OS, démarrage après redémarrage, accès depuis un appareil client et retour aux DNS automatiques.

La compatibilité avec d’autres distributions n’est pas établie. Les pannes de courant, carte SD, box ou connexion Internet ne sont pas couvertes par ces essais. Le contrôle parental est un filtrage DNS de domaines, pas une analyse des contenus des applications. Aucun blocage universel des publicités vidéo n’est annoncé.

L’administration HTTP doit rester sur un réseau local de confiance. Le script n’est pas un mécanisme de mise à niveau automatique : la version AdGuard reste épinglée.

## Reproduire les essais Linux

Sur une machine de développement adaptée, pas sur une machine de production :

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-yaml python3-bcrypt iproute2 qemu-user-static shellcheck
python3 tests/review.py
sudo python3 tests/prepare_assets.py
sudo unshare --net -- bash -c 'ip link set lo up; python3 tests/integration.py'
sudo unshare --net -- bash -c 'ip link set lo up; python3 tests/interactive_prompt.py'
sudo python3 tests/masked_input.py
sudo python3 tests/live_upstreams.py
```

Ces commandes ne sont pas nécessaires pour utiliser le paquet client. Le test réseau public contacte des résolveurs externes et n’écoute que sur loopback. Les mots de passe présents dans les tests sont des données temporaires de test, pas des identifiants de production.

Après réussite, `python3 tools/package.py` produit `.distribution/LiminalGuard.zip`. Le paquetage vérifie la correspondance des preuves avec le script et refuse des preuves périmées.
