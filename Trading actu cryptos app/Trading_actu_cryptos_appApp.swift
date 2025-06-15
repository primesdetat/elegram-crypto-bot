//
//  Trading_actu_cryptos_appApp.swift
//  Trading actu cryptos app
//
//  Created by Namous Abdelhakim on 15/06/2025.
//

import SwiftUI
import SwiftData

@main
struct Trading_actu_cryptos_appApp: App {
    var sharedModelContainer: ModelContainer = {
        let schema = Schema([
            Item.self,
        ])
        let modelConfiguration = ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)

        do {
            return try ModelContainer(for: schema, configurations: [modelConfiguration])
        } catch {
            fatalError("Could not create ModelContainer: \(error)")
        }
    }()

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .modelContainer(sharedModelContainer)
    }
}
