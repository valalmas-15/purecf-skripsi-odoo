/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PurecfMasterData extends Component {
    setup() {
        this.actionService = useService("action");
        this.state = useState({
            activeItem: 'products'
        });
    }

    openAction(xmlid, item) {
        this.state.activeItem = item;
        this.actionService.doAction(xmlid);
    }
}

PurecfMasterData.template = "purecf_erp.MasterData";
registry.category("actions").add("purecf_master_data", PurecfMasterData);
