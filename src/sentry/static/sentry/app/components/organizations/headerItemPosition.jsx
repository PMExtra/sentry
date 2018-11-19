import styled from 'react-emotion';
import {AutoCompleteRoot} from 'app/components/dropdownAutoCompleteMenu';
import {TimeRangeRoot} from 'app/components/organizations/timeRangeSelector/index.jsx';

const HeaderItemPosition = styled.div`
  display: flex;
  flex: 1;
  max-width: 450px;
  height: 100%;

  /* stylelint-disable-next-line no-duplicate-selectors */
  ${AutoCompleteRoot}, ${TimeRangeRoot} {
    flex: 1;
  }
`;

export default HeaderItemPosition;
