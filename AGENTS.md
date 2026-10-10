# EfficientUnityRipper engineering instructions

For coding, use the Headroom init-user deployment; check its local proxy health and start `headroom install start --profile init-user` if stopped. Use Caveman for concise user communication and Ponytail full for scoped implementation; documentation/code remain normal clear prose. Do not spawn agents unless the user or an applicable skill explicitly requests delegation.

Read source and contracts before editing. Preserve GPL/MIT and dependency notices. Never track/push `.local`, build/cache outputs, upstream checkouts, or game-derived assets. All real-game tests require explicit authorization and outputs outside this source repository. Do not alter game installations.

Test the actual AssetRipper importer, not a demo-manifest parser. Do not mark inferred, engine-injected, default or failed values as recovered original data. No automatic 1:1, script logic, or executable shader recovery claims. REA stays separate. Run relevant tests and capture actual rendered GUI for UI changes; report fixture vs real-game coverage.
