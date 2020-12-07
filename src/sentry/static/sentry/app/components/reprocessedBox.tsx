import React from 'react';
import styled from '@emotion/styled';

import {BannerContainer, BannerSummary} from 'app/components/events/styles';
import Link from 'app/components/links/link';
import {IconCheckmark, IconClose} from 'app/icons';
import {tct, tn} from 'app/locale';
import space from 'app/styles/space';
import {GroupActivity, GroupActivityData, Organization} from 'app/types';
import localStorage from 'app/utils/localStorage';

type Props = {
  reprocessActivity: Omit<GroupActivity, 'data'> & {
    data: NonNullable<Omit<GroupActivityData, 'text'>>;
  };
  orgSlug: Organization['slug'];
};

type State = {
  isBannerHidden: boolean;
};

class ReprocessedBox extends React.Component<Props, State> {
  state: State = {
    isBannerHidden: localStorage.getItem(this.getBannerUniqueId()) === 'true',
  };

  getBannerUniqueId() {
    const {reprocessActivity} = this.props;
    const {data, id} = reprocessActivity;
    const {newGroupId} = data;

    return `groupId-${newGroupId}-activity-${id}-banner-dismissed`;
  }

  handleBannerDismiss = () => {
    localStorage.setItem(this.getBannerUniqueId(), 'true');
    this.setState({isBannerHidden: true});
  };

  render() {
    if (this.state.isBannerHidden) {
      return null;
    }

    const {orgSlug, reprocessActivity} = this.props;
    const {data} = reprocessActivity;
    const {eventCount, oldGroupId} = data;

    return (
      <BannerContainer priority="success">
        <StyledBannerSummary>
          <IconCheckmark color="green300" isCircled />
          <span>
            {tct('Events in this issue were successfully reprocessed. [link]', {
              link: (
                <Link
                  to={`/organizations/${orgSlug}/issues/?query=reprocessing.original_issue_id:${oldGroupId}`}
                >
                  {tn('See %s new issue', 'See %s new issues', eventCount)}
                </Link>
              ),
            })}
          </span>
          <StyledIconClose
            color="green300"
            isCircled
            onClick={this.handleBannerDismiss}
          />
        </StyledBannerSummary>
      </BannerContainer>
    );
  }
}

export default ReprocessedBox;

const StyledBannerSummary = styled(BannerSummary)`
  & > svg:last-child {
    margin-right: 0;
    margin-left: ${space(1)};
  }
`;

const StyledIconClose = styled(IconClose)`
  cursor: pointer;
`;
