import { ComponentProps, withStreamlitConnection } from "streamlit-component-lib";
import SnapshotCanvas, { SnapshotArgs } from "./SnapshotCanvas";
import ModelCapture from "./ModelCapture";

const App = (props: ComponentProps) => {
  const mode = (props.args?.component as string) ?? "annotator";
  if (mode === "capture") {
    return <ModelCapture args={props.args} />;
  }
  return <SnapshotCanvas args={props.args as SnapshotArgs} />;
};

export default withStreamlitConnection(App);




