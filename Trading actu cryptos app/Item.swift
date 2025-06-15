//
//  Item.swift
//  Trading actu cryptos app
//
//  Created by Namous Abdelhakim on 15/06/2025.
//

import Foundation
import SwiftData

@Model
final class Item {
    var timestamp: Date
    
    init(timestamp: Date) {
        self.timestamp = timestamp
    }
}
