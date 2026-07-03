import { ServerAPI, ToggleField } from "decky-frontend-lib";
import { VFC, useState } from "react";
import { t } from "./i18n";


export const Developer: VFC<{ serverAPI: ServerAPI; }> = ({ }) => {
    const [firstLaunch, setFirstLaunch] = useState(localStorage.getItem('sk_firstlaunch') === 'true');

    return (
        <div>
            <ToggleField
                label={t("replay_first_launch")}
                description={t("replay_first_launch_desc")}
                checked={firstLaunch}
                onChange={(v) => { setFirstLaunch(v); localStorage.setItem('sk_firstlaunch', String(v)); }}
            />
        </div>
    );
};
